from django.utils.translation import gettext_lazy as _

class OrderStatus:
    PENDING_PAYMENT = 'pending_payment'
    PAID = 'paid'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'
    RETURNED = 'returned'
    PARTIALLY_RETURNED = 'partially_returned'

    CHOICES = [
        (PENDING_PAYMENT, _('Pending Payment')),
        (PAID, _('Paid')),
        (COMPLETED, _('Completed')),
        (CANCELLED, _('Cancelled')),
        (RETURNED, _('Returned')),
        (PARTIALLY_RETURNED, _('Partially Returned')),
    ]


class PaymentMethod:
    CASH = 'cash'
    ELECTRONIC = 'electronic'
    CREDIT_BALANCE = 'credit_balance'
    NOT_PAID = 'not_paid'
    CHEQUE = 'cheque'
    OTHER = 'other'

    CHOICES = [
        (CASH, _('Cash')),
        (ELECTRONIC, _('Electronic Payment')),
        (CREDIT_BALANCE, _('Credit Balance')),
        (NOT_PAID, _('Not Paid Yet')),
        (CHEQUE, _('Cheque')),
        (OTHER, _('Other')),
    ]


class RefundMethod:
    CASH = 'CASH'
    STORE_CREDIT = 'STORE_CREDIT'
    ELECTRONIC_REFUND = 'ELECTRONIC_REFUND'
    EXCHANGE = 'EXCHANGE'

    CHOICES = [
        (CASH, _('Cash Refund')),
        (STORE_CREDIT, _('Store Credit')),
        (ELECTRONIC_REFUND, _('Electronic Refund')),
        (EXCHANGE, _('Exchange')),
    ]


class ZatcaSubmissionStatus:
    PENDING = 'PENDING'
    SUBMITTED = 'SUBMITTED'
    ACCEPTED = 'ACCEPTED'
    REJECTED = 'REJECTED'
    FAILED = 'FAILED'

    CHOICES = [
        (PENDING, _('Pending ZATCA Submission')),
        (SUBMITTED, _('Submitted to ZATCA')),
        (ACCEPTED, _('ZATCA Accepted')),
        (REJECTED, _('ZATCA Rejected')),
        (FAILED, _('ZATCA Submission Failed')),
    ]
