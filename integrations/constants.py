from django.db import models
from django.utils.translation import gettext_lazy as _


class SystemType(models.TextChoices):
    REWAA = 'REWAA', _('Rewaa')
    QUICKBOOKS = 'QUICKBOOKS', _('QuickBooks Online')
    XERO = 'XERO', _('Xero')
    ZATCA_EINV = 'ZATCA_EINV', _('ZATCA E-Invoicing')


class SyncStatus(models.TextChoices):
    PENDING = 'PENDING', _('Pending')
    SUCCESS = 'SUCCESS', _('Success')
    FAILED = 'FAILED', _('Failed')
    RETRIED = 'RETRIED', _('Retried')


class ZatcaProcessingStatus(models.TextChoices):
    PENDING = 'PENDING', _('Pending Processing')
    ACCEPTED = 'ACCEPTED', _('Accepted by ZATCA')
    REJECTED = 'REJECTED', _('Rejected by ZATCA')
    FAILED = 'FAILED', _('Processing Failed')
    TIMEOUT = 'TIMEOUT', _('Request Timed Out')
    INVALID = 'INVALID', _('Invalid Invoice Format')


class ZatcaSubmissionStatus(models.TextChoices):
    PENDING = 'PENDING', _('Pending ZATCA Submission')
    SUBMITTED = 'SUBMITTED', _('Submitted to ZATCA')
    ACCEPTED = 'ACCEPTED', _('ZATCA Accepted')
    REJECTED = 'REJECTED', _('ZATCA Rejected')
    FAILED = 'FAILED', _('ZATCA Submission Failed')
