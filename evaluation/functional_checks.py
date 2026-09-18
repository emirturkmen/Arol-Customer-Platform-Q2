"""Checks of the API, the tools and the access model.

One script we run by hand, not a test framework. It prints one line per check and
never calls the language model, so it is free and takes about two seconds.

    cd backend && ../.venv/bin/uvicorn main:app --port 8000    (in one terminal)
    cd evaluation && ../.venv/bin/python functional_checks.py

What it checks are the rules of DOCUMENTATION.md sections 4 and 5: the company
boundary, the visibility levels, refusals that are sentences and not empty
results, and what the API returns.
"""

import json
import sys
import urllib.error
import urllib.request

sys.path.insert(0, "../backend")
from db import query_one  # noqa: E402
import tools  # noqa: E402

BASE = "http://127.0.0.1:8000/api"
PASSWORD = "arol2026"

passed = failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {detail}")


def call(path, token=None, data=None, raw=False):
    """One HTTP call; returns (status, body) and never raises on 4xx."""
    request = urllib.request.Request(BASE + path)
    if token:
        request.add_header("Authorization", "Bearer " + token)
    if data is not None:
        request.data = json.dumps(data).encode()
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
            return response.status, (body if raw else json.loads(body))
    except urllib.error.HTTPError as error:
        body = error.read()
        try:
            return error.code, json.loads(body)
        except ValueError:
            return error.code, body


def login(email, password=PASSWORD):
    return call("/login", data={"email": email, "password": password})


def user(email):
    return query_one(
        """SELECT u.*, c.companyName, c.currency FROM Users u
           JOIN Companies c ON u.companyId = c.companyId WHERE u.email = ?""",
        (email,),
    )


def refused(result):
    """A refusal comes back as a sentence in an 'error' field."""
    return isinstance(result, dict) and "ACCESS DENIED" in str(result.get("error", ""))


def api_checks():
    print("\n== authentication ==")
    status, body = login("matteo.bonetti@valgrande.example", "wrong")
    check("wrong password refused",
          status == 401 and body["detail"] == "Wrong email address or password", body)
    status, body = login("nobody@nowhere.example")
    check("unknown address gives the same message",
          status == 401 and body["detail"] == "Wrong email address or password", body)
    check("no token -> 401", call("/me")[0] == 401)
    check("invalid token -> 401", call("/me", token="deadbeef")[0] == 401)
    status, body = login("MATTEO.BONETTI@Valgrande.Example")
    check("the e-mail address is case-insensitive", status == 200 and "token" in body, body)

    tokens = {}
    for email, visibility in [("matteo.bonetti@valgrande.example", "technician"),
                              ("davide.ranieri@valgrande.example", "commercial"),
                              ("elena.fabbri@valgrande.example", "full")]:
        tokens[visibility] = login(email)[1]["token"]
        check(f"/me reports {visibility}",
              call("/me", token=tokens[visibility])[1].get("visibility") == visibility)

    print("\n== fleet ==")
    status, fleet = call("/machines", token=tokens["technician"])
    check("the fleet of the company is listed", status == 200 and len(fleet) == 3, fleet)
    serial = fleet[0]["serialNumber"]
    status, machine = call("/machines/" + serial, token=tokens["technician"])
    check("a machine is addressable by serial number", status == 200, machine)
    check("a machine is addressable by machine id",
          call("/machines/" + machine["machineId"], token=tokens["technician"])[0] == 200)
    check("the model of the machine is joined", bool(machine.get("model", {}).get("modelCode")))
    check("an unknown machine gives 404", call("/machines/MCH-0099", token=tokens["technician"])[0] == 404)

    print("\n== tenant boundary ==")
    ours, theirs = "15610", "A2055"     # CMP-001 and CMP-002
    check("another company's machine gives 404",
          call("/machines/" + theirs, token=tokens["technician"])[0] == 404)
    check("another company's manual gives 404",
          call(f"/machines/{theirs}/manual?token=" + tokens["technician"])[0] == 404)
    check("another company's QR code gives 404",
          call(f"/machines/{theirs}/qr?token=" + tokens["technician"])[0] == 404)
    other = login("adrien.lemaitre@bruyere.example")[1]["token"]
    status, fleet = call("/machines", token=other)
    check("the other company sees its own machines",
          sorted(m["serialNumber"] for m in fleet) == ["A2055", "A2132"], fleet)
    check("our machines are invisible to them", call("/machines/" + ours, token=other)[0] == 404)
    empty = login("mariana.esteves@cascais.example")[1]["token"]
    check("a company without machines gets an empty fleet", call("/machines", token=empty)[1] == [])

    print("\n== manual, QR code and history ==")
    status, body = call(f"/machines/{ours}/manual?token=" + tokens["technician"], raw=True)
    check("the manual is served as a PDF", status == 200 and body[:4] == b"%PDF")
    status, body = call(f"/machines/{ours}/qr?token=" + tokens["technician"], raw=True)
    check("the QR code is served as a PNG", status == 200 and body[:8] == b"\x89PNG\r\n\x1a\n")
    check("the manual needs a session",
          call(f"/machines/{ours}/manual?token=nope", raw=True)[0] == 401)
    check("a new session has no history",
          call(f"/chat/history?machine={ours}", token=tokens["technician"])[1] == [])
    check("no history is returned for another company's machine",
          call(f"/chat/history?machine={theirs}", token=tokens["technician"])[1] == [])


def tool_checks():
    technician = user("matteo.bonetti@valgrande.example")
    commercial = user("davide.ranieri@valgrande.example")
    everything = user("elena.fabbri@valgrande.example")

    print("\n== identity domain: every visibility level ==")
    for label, account in [("technician", technician), ("commercial", commercial),
                           ("full", everything)]:
        check(f"list_machines works for {label}",
              len(tools.list_machines(account).get("machines", [])) == 3)
    check("machine details carry the configuration profile",
          "configurationProfile" in tools.get_machine_details(technician, "15610"))
    first = tools.search_manual(technician, "15610", "safety procedures before maintenance")
    check("search_manual returns pages", bool(first.get("passages")))
    check("search_manual is filtered by serial number", first.get("serialNumber") == "15610")
    second = tools.search_manual(technician, "17203", "safety procedures before maintenance")
    check("another machine returns other pages of another manual",
          [p["page"] for p in second["passages"]] != [p["page"] for p in first["passages"]])

    print("\n== operational domain: full and technician only ==")
    for name in ["get_telemetry_summary", "get_recent_telemetry", "get_alarms",
                 "get_alarm_statistics", "get_maintenance_tickets"]:
        tool = getattr(tools, name)
        check(f"{name}: technician allowed", "error" not in tool(technician, "15610"))
        check(f"{name}: full allowed", "error" not in tool(everything, "15610"))
        check(f"{name}: commercial refused with a sentence", refused(tool(commercial, "15610")))

    print("\n== commercial domain: full and commercial only ==")
    quotes = tools.list_quotes(commercial)
    check("list_quotes: commercial allowed", "error" not in quotes)
    check("list_quotes: technician refused with a sentence", refused(tools.list_quotes(technician)))
    orders = tools.list_orders(commercial)
    check("list_orders: commercial allowed", "error" not in orders)
    check("list_orders: technician refused with a sentence", refused(tools.list_orders(technician)))
    quote_id = quotes["quotes"][0]["quoteId"]
    details = tools.get_quote_details(commercial, quote_id)
    check("get_quote_details: commercial allowed", "error" not in details)
    check("get_quote_details: technician refused",
          refused(tools.get_quote_details(technician, quote_id)))
    check("the status shown is the one of the highest revision",
          quotes["quotes"][0]["currentRevision"]["revisionNumber"]
          == max(r["revisionNumber"] for r in details["revisions"]))
    check("get_order_details: commercial allowed",
          "error" not in tools.get_order_details(commercial, orders["orders"][0]["orderId"]))

    print("\n== tenant boundary inside the tools ==")
    check("machine of another company: not in your fleet",
          "not part of their fleet" in str(tools.get_machine_details(technician, "A2055")))
    check("manual of another company refused", "error" in tools.search_manual(technician, "A2055", "safety"))
    check("telemetry of another company refused", "error" in tools.get_telemetry_summary(technician, "A2055"))
    check("quote of another company refused",
          "error" in tools.get_quote_details(user("solene.vasseur@bruyere.example"), quote_id))
    check("a company without machines gets an explicit note",
          tools.list_machines(user("rui.cardoso@cascais.example")).get("note") is not None)


def main():
    try:
        api_checks()
    except urllib.error.URLError:
        print("The backend is not running on port 8000: start it before this script.")
        return 1
    tool_checks()
    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
