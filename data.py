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
        iom_ids=["6", "7", "8"],
    ),
    Task(
        id="2",
        company_id="1",
        prompt="Generate code output",
        iom_ids=["1", "3", "5"],
    ),
    Task(
        id="3",
        company_id="1",
        prompt="Solve exam",
        iom_ids=["3", "4"],
    )
]

# TODO: maybe split out website - we need to know what we're detecting on it
# e.g. some websites we want to detect abuse on, some of them exist as purely content to host canaries
canary_types = [
    CanaryType(
        id="1",
        name="Website",
    ),
    CanaryType(
        id="2",
        name="Database",
    ),
    CanaryType(
        id="3",
        name="Credential"
    ),
    CanaryType(
        id="4",
        name="Message board"
    ),
    CanaryType(
        id="5",
        name="GitHub repository",
    ),
    CanaryType(
        id="6",
        name="LinkedIn user",
    ),
    CanaryType(
        id="7",
        name="GitHub user",
    )
]

ioms = [
    IOM(id="1", name="Message board collusion", linked_canary_type_ids=["4"]),
    # TODO(CONTRACT.md open question 3): "" is not a real CanaryType id - unclear
    # whether this should mean "no canary type covers this yet" or is a data bug.
    IOM(id="2", name="Task dependency server exploitation", linked_canary_type_ids=[""]),
    IOM(id="3", name="Cheating via dataset answers to the task online", linked_canary_type_ids=["1", "2", "5"]),
    IOM(id="4", name="Usage of stolen canary credentials on target websites", linked_canary_type_ids=["3"]),
    IOM(id="5", name="Exploitation of personality generation", linked_canary_type_ids=["5", "6", "7"]),
    IOM(id="6", name="Internal network exploitation", linked_canary_type_ids=[]),
    IOM(id="7", name="Internal network enumeration", linked_canary_type_ids=[]),
    IOM(id="8", name="Unauthorised internet access", linked_canary_type_ids=["1"]),
]

# TODO: instances agents.py generates always stay deployment_health="pending"
# forever - there's no deploy step that ever flips them to "active". task_id
# is patched on in rfc/api.py (not set at the source in agents.py); iom_ids
# is now set at the source (see rfc.agents.save_predicted_canary_instances).
canary_instances: list[CanaryInstance] = []

canary_events: list[CanaryEvent] = []