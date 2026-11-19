"""Cloud-safe setup for GMAO Notifications & Alerting."""

from maintenance_app.notifications.install import (
    install_notification_contact_fields,
    copy_legacy_external_contact_role,
)
from maintenance_app.notifications.profile_install import (
    install_gmao_notification_profiles,
)


def install_gmao_notifications():
    """Install missing configuration without overwriting existing settings."""
    install_notification_contact_fields()
    install_gmao_notification_profiles()
    copy_legacy_external_contact_role()
