"""Access model: company (tenant) plus visibility level.

Both checks must pass before any data is returned, and a request outside the
user's scope is refused in words, never with an empty result.
"""

from db import query_one

# Which visibility levels may read each data domain.
DOMAIN_PERMISSIONS = {
    # Machines, models and manuals: visible to every user of the owning company.
    "identity": ("full", "technician", "commercial"),
    # Telemetry, alarms, maintenance tickets.
    "operational": ("full", "technician"),
    # Quotes, revisions, lines, orders, order lines.
    "commercial": ("full", "commercial"),
}

DENIED_MESSAGE = {
    "operational": (
        "ACCESS DENIED: this user has 'commercial' visibility and is not allowed to read "
        "telemetry, alarms or maintenance data. Tell the user their account does not have "
        "access to operational data and that a technician account is required."
    ),
    "commercial": (
        "ACCESS DENIED: this user has 'technician' visibility and is not allowed to read "
        "quotes or orders. Tell the user their account does not have access to commercial "
        "data and that a commercial account is required."
    ),
}


def can_access(user, domain):
    return user["visibility"] in DOMAIN_PERMISSIONS[domain]


def denied(domain):
    return {"error": DENIED_MESSAGE[domain]}


def get_machine(user, machine_ref):
    """Find a machine by machineId or serialNumber, inside the user's company only.

    Returns None both when the machine does not exist and when it belongs to
    another company. We answer the same way in the two cases.
    """
    if not machine_ref:
        return None
    return query_one(
        "SELECT * FROM Machines WHERE (machineId = ? OR serialNumber = ?) AND companyId = ?",
        (str(machine_ref).strip(), str(machine_ref).strip(), user["companyId"]),
    )


def machine_not_found(machine_ref):
    return {
        "error": (
            f"No machine '{machine_ref}' is registered to this user's company. "
            "Tell the user the machine is not part of their fleet."
        )
    }
