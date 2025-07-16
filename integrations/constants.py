# integrations/constants.py
SYSTEM_TYPE_CHOICES = (
    ('REWAA', 'Rewaa'),
    ('QUICKBOOKS', 'QuickBooks Online'),
    ('XERO', 'Xero'),
    ('ZATCA_EINV', 'ZATCA E-Invoicing'),
)

SYNC_STATUS_CHOICES = (
    ('PENDING', 'Pending'),
    ('SUCCESS', 'Success'),
    ('FAILED', 'Failed'),
    ('RETRIED', 'Retried'),
)

ZATCA_PROCESSING_STATUS_CHOICES = (
    ('PENDING', 'Pending Processing'),
    ('ACCEPTED', 'Accepted by ZATCA'),
    ('REJECTED', 'Rejected by ZATCA'),
    ...
)
