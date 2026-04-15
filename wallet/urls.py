from django.urls import path

from . import views

urlpatterns = [
    path('', views.dashboard_view, name='home'),
    path('login', views.login_view, name='login'),
    path('register', views.register_view, name='register'),
    path('logout', views.logout_view, name='logout'),
    path('dashboard', views.dashboard_view, name='dashboard'),
    path('add-transaction', views.add_transaction_view, name='add_transaction'),
    path('transaction-success', views.transaction_success_view, name='transaction_success'),
    path('history', views.history_view, name='history'),
    path('category/<int:pk>', views.category_detail_view, name='category_detail'),
    path('assistant', views.assistant_view, name='assistant'),
]
