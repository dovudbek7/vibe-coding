from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.paginator import Paginator
from django.db.models import Case, DecimalField, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce, TruncDate
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods

from .forms import RegistrationForm, TransactionForm
from .models import Category, Transaction

DEFAULT_CATEGORIES = [
    ('Food', 'restaurant'),
    ('Transport', 'directions_car'),
    ('Salary', 'payments'),
    ('Shopping', 'shopping_bag'),
    ('Health', 'favorite'),
    ('Entertainment', 'movie'),
    ('Bills', 'receipt_long'),
]

CURRENCY_RATES = {
    'USD': Decimal('1'),
    'UZS': Decimal('12850'),
    'EUR': Decimal('0.92'),
}


def ensure_default_categories(user):
    if user.categories.exists():
        return

    # A new account should be usable immediately without manual category setup.
    Category.objects.bulk_create(
        [
            Category(user=user, name=name, icon=icon)
            for name, icon in DEFAULT_CATEGORIES
        ]
    )


def _user_totals(user):
    totals = user.transactions.aggregate(
        income=Coalesce(
            Sum('amount', filter=Q(type=Transaction.TransactionType.INCOME)),
            Decimal('0'),
        ),
        expense=Coalesce(
            Sum('amount', filter=Q(type=Transaction.TransactionType.EXPENSE)),
            Decimal('0'),
        ),
    )
    totals['balance'] = totals['income'] - totals['expense']
    return totals


def _conversion_context(balance):
    return {
        code: (balance * rate).quantize(Decimal('0.01'))
        for code, rate in CURRENCY_RATES.items()
    }


def _store_success_transaction(request, transaction):
    request.session['latest_transaction_success'] = {
        'title': transaction.title,
        'amount': f'{transaction.amount:.2f}',
        'type': transaction.get_type_display(),
        'category': transaction.category.name,
        'created_at': timezone.localtime(transaction.created_at).strftime('%b %d, %Y %H:%M'),
    }


def _assistant_reply(user, message):
    lowered = message.lower()
    totals = _user_totals(user)

    # Keep the assistant deterministic for an MVP: quick, explainable, no external API.
    if 'balance' in lowered:
        return f"Your current balance is ${totals['balance']:.2f}."

    if 'income' in lowered:
        return f"Your total income is ${totals['income']:.2f}."

    if 'expense' in lowered or 'spent' in lowered:
        top_category = (
            user.transactions.filter(type=Transaction.TransactionType.EXPENSE)
            .values('category__name')
            .annotate(total=Sum('amount'))
            .order_by('-total')
            .first()
        )
        if top_category:
            return (
                f"You spent most on {top_category['category__name']} "
                f"(${top_category['total']:.2f})."
            )
        return 'You have no expense data yet.'

    recent_count = user.transactions.count()
    if recent_count == 0:
        return 'Start by adding your first transaction, and I will analyze it for you.'

    return (
        f"I found {recent_count} transactions so far. Ask me about your balance, "
        'income, or spending to get a quick insight.'
    )


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    form = RegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        ensure_default_categories(user)
        login(request, user)
        messages.success(request, 'Your account has been created successfully.')
        return redirect('dashboard')
    return render(request, 'wallet/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        messages.success(request, 'Welcome back.')
        return redirect('dashboard')
    return render(request, 'wallet/login.html', {'form': form})


@login_required
@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('login')


@login_required
def dashboard_view(request):
    ensure_default_categories(request.user)
    totals = _user_totals(request.user)
    recent_transactions = request.user.transactions.select_related('category')[:5]
    chart_rows = (
        request.user.transactions.annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(
            income=Coalesce(
                Sum('amount', filter=Q(type=Transaction.TransactionType.INCOME)),
                Decimal('0'),
            ),
            expense=Coalesce(
                Sum('amount', filter=Q(type=Transaction.TransactionType.EXPENSE)),
                Decimal('0'),
            ),
        )
        .order_by('day')[:7]
    )

    context = {
        'totals': totals,
        'recent_transactions': recent_transactions,
        'currency_totals': _conversion_context(totals['balance']),
        'chart_labels': [row['day'].strftime('%b %d') for row in chart_rows],
        'chart_income': [float(row['income']) for row in chart_rows],
        'chart_expense': [float(row['expense']) for row in chart_rows],
    }
    return render(request, 'wallet/dashboard.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def add_transaction_view(request):
    ensure_default_categories(request.user)
    form = TransactionForm(request.POST or None, user=request.user)

    if request.method == 'POST' and form.is_valid():
        transaction = form.save(commit=False)
        transaction.user = request.user
        transaction.save()
        _store_success_transaction(request, transaction)
        messages.success(request, 'Transaction saved successfully.')

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse(
                {
                    'success': True,
                    'message': 'Transaction saved successfully.',
                    'redirect_url': '/transaction-success',
                }
            )
        return redirect('transaction_success')

    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    return render(request, 'wallet/add_transaction.html', {'form': form})


@login_required
def transaction_success_view(request):
    transaction_data = request.session.pop('latest_transaction_success', None)
    if not transaction_data:
        messages.info(request, 'Add a transaction first to see the success page.')
        return redirect('add_transaction')

    return render(
        request,
        'wallet/transaction_success.html',
        {'transaction': transaction_data},
    )


@login_required
def history_view(request):
    ensure_default_categories(request.user)
    transactions = request.user.transactions.select_related('category')
    selected_date = request.GET.get('date')
    selected_category = request.GET.get('category')
    view_mode = request.GET.get('view', 'all')

    if selected_date:
        transactions = transactions.filter(created_at__date=selected_date)
    if selected_category:
        transactions = transactions.filter(category_id=selected_category)

    paginator = Paginator(transactions, 8)
    page_obj = paginator.get_page(request.GET.get('page'))

    categories = request.user.categories.all()
    grouped_categories = []
    if view_mode == 'category':
        # Summarize per category first, then attach the matching transactions for the folder view.
        summary_rows = (
            transactions.values('category_id', 'category__name', 'category__icon')
            .annotate(
                total_income=Coalesce(
                    Sum('amount', filter=Q(type=Transaction.TransactionType.INCOME)),
                    Decimal('0'),
                ),
                total_expense=Coalesce(
                    Sum('amount', filter=Q(type=Transaction.TransactionType.EXPENSE)),
                    Decimal('0'),
                ),
                net_total=Coalesce(
                    Sum(
                        Case(
                            When(
                                type=Transaction.TransactionType.INCOME,
                                then=F('amount'),
                            ),
                            When(
                                type=Transaction.TransactionType.EXPENSE,
                                then=F('amount') * Value(-1),
                            ),
                            default=Value(0),
                            output_field=DecimalField(max_digits=12, decimal_places=2),
                        )
                    ),
                    Decimal('0'),
                ),
            )
            .order_by('category__name')
        )
        transaction_map = {}
        for item in transactions:
            transaction_map.setdefault(item.category_id, []).append(item)

        for row in summary_rows:
            grouped_categories.append(
                {
                    'id': row['category_id'],
                    'name': row['category__name'],
                    'icon': row['category__icon'] or 'folder',
                    'total_income': row['total_income'],
                    'total_expense': row['total_expense'],
                    'net_total': row['net_total'],
                    'transactions': transaction_map.get(row['category_id'], []),
                }
            )

    context = {
        'page_obj': page_obj,
        'categories': categories,
        'grouped_categories': grouped_categories,
        'selected_date': selected_date or '',
        'selected_category': selected_category or '',
        'view_mode': view_mode,
    }
    return render(request, 'wallet/history.html', context)


@login_required
def category_detail_view(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)
    transactions = category.transactions.filter(user=request.user)
    totals = transactions.aggregate(
        income=Coalesce(
            Sum('amount', filter=Q(type=Transaction.TransactionType.INCOME)),
            Decimal('0'),
        ),
        expense=Coalesce(
            Sum('amount', filter=Q(type=Transaction.TransactionType.EXPENSE)),
            Decimal('0'),
        ),
    )
    totals['balance'] = totals['income'] - totals['expense']
    return render(
        request,
        'wallet/category_detail.html',
        {
            'category': category,
            'transactions': transactions,
            'totals': totals,
        },
    )


@login_required
@require_http_methods(['GET', 'POST'])
def assistant_view(request):
    history = request.session.get('assistant_history', [])

    if request.method == 'POST':
        message = request.POST.get('message', '').strip()
        if message:
            reply = _assistant_reply(request.user, message)
            history.append({'role': 'user', 'message': message})
            history.append({'role': 'assistant', 'message': reply})
            request.session['assistant_history'] = history[-12:]
            messages.success(request, 'Assistant response generated.')
            return redirect('assistant')
        messages.error(request, 'Please enter a message.')

    if not history:
        history = [
            {
                'role': 'assistant',
                'message': 'Ask me about your balance, income, or where you spent most.',
            }
        ]
        request.session['assistant_history'] = history

    return render(request, 'wallet/assistant.html', {'chat_history': history})
