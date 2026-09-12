from rfc.models import Dashboard, Company, Task, IOM, CanaryType, CanaryInstance, CanaryEvent

"""
Internet access
Just monitor access to a server

Message board collusion - [Communication via Unauthorised Channels]
Generate realistic looking message boards
Perform some SEO “poisoning” to come up in AI search path
Encoded messages left by agents - need to see how messages were encoded during HF attack

Task dependency server exploitation
Put websites in plausible locations, e.g. for Elsa toys create “elsa-toys[.]com”
Make honeypots that the agent might rely on
Monitor for suspicious activity
SEO poisoning

Cheating via canary dataset answers to the task online
GitHub repositories
Websites (like PDF of Q/A), personal blogs - need SEO poisoning
“Exposed” DB credentials or database backups

Usage of stolen canary credentials to target websites
GitHub repositories
Websites, personal blogs
“Exposed” .env leaving API keys

Exploitation of personality generation
LinkedIn message
GitHub PRs being opened
Internal network exploitation
Internal network enumeration

"""

dashboard = Dashboard(managed_company_ids=["1"])

companies = [
    Company(
        id="1",
        name="Deutsche Bank",
        domains=["db.com"],
        compliance_status="SOC2 compliant",
    )
]

tasks = [
    Task(
        id="1",
        company_id="1",
        prompt="RAG on company data",
    ),
    Task(
        id="2",
        company_id="1",
        prompt="Generate code output",
    ),
    Task(
        id="3",
        company_id="1",
        prompt="Solve exam",
    )
]

canary_types = [
    CanaryType(
        id="1",
        name="Impersonation server",
    ),
    CanaryType(
        id="2",
        name="Fake answers canary",
    ),
    CanaryType(
        id="4",
        name="Message board"
    ),
    # CanaryType(
    #     id="6",
    #     name="LinkedIn user",
    # ),
    # CanaryType(
    #     id="7",
    #     name="GitHub user",
    # )
]

ioms = [
    IOM(id="1", name="Message board collusion", linked_canary_type_ids=["4"]),
    # TODO(CONTRACT.md open question 3): "" is not a real CanaryType id - unclear
    # whether this should mean "no canary type covers this yet" or is a data bug.
    IOM(id="2", name="Third-party server exploitation", linked_canary_type_ids=["1"]),
    IOM(id="3", name="Cheating via dataset answers to the task online", linked_canary_type_ids=["1", "2"]),
    IOM(id="4", name="Usage of stolen credentials", linked_canary_type_ids=["1", "4"]),
    IOM(id="5", name="Exploitation of personality", linked_canary_type_ids=[]),
    IOM(id="6", name="Internal network exploitation", linked_canary_type_ids=[]),
    IOM(id="7", name="Internal network enumeration", linked_canary_type_ids=[]),
    IOM(id="8", name="Unauthorised internet access", linked_canary_type_ids=["1"]),
]

# TODO: rfc/agents.py's save_predicted_canary_instances() doesn't populate
# task_id/iom_ids/deployment_health/etc. on the CanaryInstance it creates -
# needs a task_id (and ideally iom_ids) parameter threaded through from the
# caller before agent-predicted canaries are usable by the API/frontend.
canary_instances: list[CanaryInstance] = []

canary_events: list[CanaryEvent] = []