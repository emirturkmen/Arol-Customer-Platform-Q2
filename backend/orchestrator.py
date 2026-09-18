"""The orchestrator: picks one agent for a question and runs it.

For every user message:
  1. ask the model which agent handles the question,
  2. check the user's visibility against that agent's data domain,
  3. run the agent in a tool-calling loop,
  4. return the answer, the agent used and the manual pages cited.
"""

import json
import logging
import time
from datetime import datetime

import access
import llm
from agents import AGENTS, IMPLEMENTATIONS, tool_definitions
from config import TODAY
from db import execute, query

logger = logging.getLogger("arol")

MAX_TOOL_ROUNDS = 4
HISTORY_LENGTH = 6  # previous messages kept as conversation memory

ROUTER_PROMPT = """You route a user question to one handler. Answer with one word only.

manuals: {manuals}
diagnostics: {diagnostics}
commercial: {commercial}
general: greetings and questions about the platform itself, never a question about data.

What a machine is always goes to manuals, even when it sounds technical: which
machines the company owns, the model, the serial number, the as-built configuration,
the number of heads, the nominal production rate, the supply voltage. Choose
diagnostics only for how a machine is running now or for a problem to solve.

Answer with exactly one of: manuals, diagnostics, commercial, general."""

GENERAL_PROMPT = """You are the assistant of the AROL Customer Platform, which gives plant
operators access to their machines: manuals, telemetry and alarms, maintenance and commercial
documents. Reply briefly and, if useful, say what the user can ask you. Do not invent data."""


def _router_prompt():
    return ROUTER_PROMPT.format(**{name: AGENTS[name]["handles"] for name in AGENTS})


def route(message):
    """Choose the handler for a message; fall back to the manuals agent."""
    reply = llm.chat([
        {"role": "system", "content": _router_prompt()},
        {"role": "user", "content": message},
    ])
    answer = (reply.content or "").strip().lower()
    for name in list(AGENTS) + ["general"]:
        if name in answer:
            return name
    return "manuals"


def _system_prompt(agent_name, user, machine):
    agent = AGENTS[agent_name]
    lines = [
        agent["instructions"],
        "",
        f"Today is {TODAY}.",
        f"You are talking to {user['firstName']} {user['lastName']} ({user['jobTitle']}) "
        f"of {user['companyName']}.",
        "Use the tools to get data: never invent machines, numbers, codes or prices. "
        "If a tool returns an error, explain it to the user. "
        # No table records how many hours a machine has run, so the interval can be
        # quoted but the due date cannot be computed. AROL confirmed we should say so.
        "The manuals give maintenance intervals in working hours, but the platform does "
        "not record how many hours a machine has run. If asked when maintenance is due, "
        "give the interval from the manual and say that the accumulated running hours "
        "are not available, instead of estimating them. "
        "Answer in a few short sentences or a short list.",
    ]
    if machine:
        lines.append(
            f"The user is currently looking at machine {machine['machineId']} "
            f"(serial number {machine['serialNumber']}, {machine['plantLocation']}). "
            "Use this machine when the user does not name another one."
        )
    return "\n".join(lines)


def _history(token, machine_id):
    """The last messages of this session about this machine.

    The machine filter matters: without it, the turns about the previous machine
    would arrive as context for the new one.
    """
    rows = query(
        """SELECT role, content FROM Messages
           WHERE token = ? AND machineId IS ? ORDER BY messageId DESC LIMIT ?""",
        (token, machine_id, HISTORY_LENGTH),
    )
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def _save(token, machine_id, role, content, agent=None, sources=None):
    execute(
        """INSERT INTO Messages (token, machineId, role, content, agent, sources, createdAt)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (token, machine_id, role, content, agent,
         json.dumps(sources) if sources else None,
         datetime.now().isoformat(timespec="seconds")),
    )


def _run_agent(agent_name, user, machine, message, history):
    """Run one agent until it answers. Returns (answer, cited manual pages)."""
    messages = [{"role": "system", "content": _system_prompt(agent_name, user, machine)}]
    messages += history
    messages.append({"role": "user", "content": message})
    definitions = tool_definitions(agent_name)
    sources = []

    for _ in range(MAX_TOOL_ROUNDS):
        reply = llm.chat(messages, tools=definitions)
        calls = reply.tool_calls or []
        if not calls:
            return (reply.content or "").strip(), sources

        messages.append(reply)
        for call in calls:
            name = call.function.name
            arguments = json.loads(call.function.arguments or "{}")
            if name in AGENTS[agent_name]["tools"]:
                result = IMPLEMENTATIONS[name](user, **arguments)
            else:
                result = {"error": f"Unknown tool '{name}'."}
            logger.info("tool %s %s -> %s", name, arguments,
                        "error" if "error" in result else "ok")
            if name == "search_manual" and "passages" in result:
                sources += [
                    {"serialNumber": result["serialNumber"], "page": p["page"]}
                    for p in result["passages"]
                ]
            # The result goes back as text, linked to the call that asked for it.
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result, ensure_ascii=False)[:6000],
            })

    # The model kept calling tools: ask it once more for a plain answer.
    messages.append({"role": "user", "content": "Answer now, without calling any more tools."})
    reply = llm.chat(messages)
    return (reply.content or "").strip(), sources


def handle_message(user, token, message, machine):
    """Entry point used by the API for one chat turn."""
    started = time.time()
    machine_id = machine["machineId"] if machine else None
    # Read the memory before saving, so it holds the previous turns and not this one.
    history = _history(token, machine_id)
    _save(token, machine_id, "user", message)
    agent_name = route(message)

    if agent_name == "general":
        reply = llm.chat(
            [{"role": "system", "content": GENERAL_PROMPT}] + history +
            [{"role": "user", "content": message}]
        )
        answer, sources = (reply.content or "").strip(), []
    elif not access.can_access(user, AGENTS[agent_name]["domain"]):
        # Refuse in words. An empty answer would look like "there is no data".
        answer = (
            f"Your account has '{user['visibility']}' visibility, which does not include "
            f"{AGENTS[agent_name]['domain']} data, so I cannot answer this question. "
            "Please ask a colleague whose account covers it."
        )
        sources = []
    else:
        answer, sources = _run_agent(agent_name, user, machine, message, history)

    _save(token, machine_id, "assistant", answer, agent_name, sources)
    logger.info("turn user=%s visibility=%s agent=%s machine=%s seconds=%.1f",
                user["email"], user["visibility"], agent_name,
                machine["machineId"] if machine else "-", time.time() - started)
    return {"answer": answer, "agent": agent_name, "sources": sources}
