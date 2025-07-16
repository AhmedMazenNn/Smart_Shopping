from django.db import models
from django.utils.translation import gettext_lazy as _


class OrderStatus(models.TextChoices):
    PENDING_PAYMENT = 'pending_payment', _('Pending Payment')
    PAID = 'paid', _('Paid')
    COMPLETED = 'completed', _('Completed')
    CANCELLED = 'cancelled', _('Cancelled')
    RETURNED = 'returned', _('Returned')
    PARTIALLY_RETURNED = 'partially_returned', _('Partially Returned')


class PaymentMethod(models.TextChoices):
    CASH = 'cash', _('Cash')
    ELECTRONIC = 'electronic', _('Electronic Payment')
    CREDIT_BALANCE = 'credit_balance', _('Credit Balance')
    NOT_PAID = 'not_paid', _('Not Paid Yet')
    CHEQUE = 'cheque', _('Cheque')
    OTHER = 'other', _('Other')


class RefundMethod(models.TextChoices):
    CASH = 'CASH', _('Cash Refund')
    STORE_CREDIT = 'STORE_CREDIT', _('Store Credit')
    ELECTRONIC_REFUND = 'ELECTRONIC_REFUND', _('Electronic Refund')
    EXCHANGE = 'EXCHANGE', _('Exchange')


class ZatcaSubmissionStatus(models.TextChoices):
    PENDING = 'PENDING', _('Pending ZATCA Submission')
    SUBMITTED = 'SUBMITTED', _('Submitted to ZATCA')
    ACCEPTED = 'ACCEPTED', _('ZATCA Accepted')
    REJECTED = 'REJECTED', _('ZATCA Rejected')
    FAILED = 'FAILED', _('ZATCA Submission Failed')
