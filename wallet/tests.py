from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Category, Transaction


class WalletViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='first@example.com',
            email='first@example.com',
            password='StrongPass123',
            first_name='First User',
        )
        self.other_user = User.objects.create_user(
            username='second@example.com',
            email='second@example.com',
            password='StrongPass123',
            first_name='Second User',
        )
        self.user_category = Category.objects.create(
            user=self.user,
            name='Food',
            icon='restaurant',
        )
        self.other_category = Category.objects.create(
            user=self.other_user,
            name='Travel',
            icon='flight',
        )

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_category_detail_is_scoped_to_logged_in_user(self):
        self.client.login(username='first@example.com', password='StrongPass123')
        response = self.client.get(reverse('category_detail', args=[self.other_category.id]))
        self.assertEqual(response.status_code, 404)

    def test_ajax_transaction_add_creates_user_owned_record(self):
        self.client.login(username='first@example.com', password='StrongPass123')
        response = self.client.post(
            reverse('add_transaction'),
            {
                'title': 'Lunch',
                'amount': '25.50',
                'category': self.user_category.id,
                'type': 'expense',
                'note': 'Team lunch',
                'created_at': timezone.localtime().strftime('%Y-%m-%dT%H:%M'),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['redirect_url'], '/transaction-success')
        self.assertEqual(Transaction.objects.filter(user=self.user).count(), 1)
        self.assertEqual(Transaction.objects.filter(user=self.other_user).count(), 0)

    def test_success_page_shows_latest_transaction_summary(self):
        self.client.login(username='first@example.com', password='StrongPass123')
        response = self.client.post(
            reverse('add_transaction'),
            {
                'title': 'Salary',
                'amount': '500.00',
                'category': self.user_category.id,
                'type': 'income',
                'note': '',
                'created_at': timezone.localtime().strftime('%Y-%m-%dT%H:%M'),
            },
            follow=True,
        )
        self.assertRedirects(response, reverse('transaction_success'))
        self.assertContains(response, 'Salary')

# Create your tests here.
