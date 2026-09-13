/**
 * Static (frontend-only) mapping from each canarynet IOM to the closest
 * MITRE ATT&CK (Enterprise) tactic/technique, for the audit report - not
 * part of the backend/CONTRACT.md data model since it's descriptive
 * reference content, not something the API returns or a canary reads.
 *
 * IOMs describe an *AI agent's* misaligned behavior, not a human
 * adversary's, so most mappings below are best-fit analogies rather than
 * literal matches - ATT&CK was written for human-operated intrusions
 * against enterprise IT. Where an IOM is an AI-native behavior with no
 * reasonable Enterprise ATT&CK analog (personality/persona exploitation,
 * i.e. jailbreaking), MITRE ATLAS - the sibling framework for AI-system
 * attacks - is the more honest fit and is called out as such.
 *
 * Keep this in sync with `data.py`'s `ioms` list by `id`.
 */

export interface MitreTechnique {
  id: string;
  name: string;
  url: string;
}

export interface MitreMapping {
  iomId: string;
  framework: "attack" | "atlas";
  tactic: string;
  techniques: MitreTechnique[];
  rationale: string;
}

export const MITRE_MAPPING: MitreMapping[] = [
  {
    iomId: "1",
    framework: "attack",
    tactic: "Command and Control",
    techniques: [
      { id: "T1102", name: "Web Service", url: "https://attack.mitre.org/techniques/T1102/" },
      {
        id: "T1567",
        name: "Exfiltration Over Web Service",
        url: "https://attack.mitre.org/techniques/T1567/",
      },
    ],
    rationale:
      "An agent coordinating with other agent instances (or leaking task state) via a public message board is using a legitimate, third-party web service as a covert channel - the same pattern ATT&CK captures as using web services for C2 or as an exfiltration destination, just with agents instead of implants on either end.",
  },
  {
    iomId: "2",
    framework: "attack",
    tactic: "Initial Access",
    techniques: [
      {
        id: "T1190",
        name: "Exploit Public-Facing Application",
        url: "https://attack.mitre.org/techniques/T1190/",
      },
    ],
    rationale:
      "The agent reaches beyond its intended task scope to attack a third-party server it was never authorized to touch - functionally identical to an adversary's first foothold via a vulnerable public-facing service, just self-directed rather than operator-directed.",
  },
  {
    iomId: "3",
    framework: "attack",
    tactic: "Reconnaissance",
    techniques: [
      {
        id: "T1593",
        name: "Search Open Websites/Domains",
        url: "https://attack.mitre.org/techniques/T1593/",
      },
      {
        id: "T1596",
        name: "Search Open Technical Databases",
        url: "https://attack.mitre.org/techniques/T1596/",
      },
    ],
    rationale:
      "Finding a leaked answer key or benchmark solution online instead of solving the task legitimately is passive open-source information gathering aimed at the task itself - the same tactic ATT&CK assigns to an adversary scouring public sources for information to reach a goal without doing the underlying work.",
  },
  {
    iomId: "4",
    framework: "attack",
    tactic: "Credential Access",
    techniques: [
      {
        id: "T1552.001",
        name: "Unsecured Credentials: Credentials In Files",
        url: "https://attack.mitre.org/techniques/T1552/001/",
      },
      { id: "T1078", name: "Valid Accounts", url: "https://attack.mitre.org/techniques/T1078/" },
    ],
    rationale:
      "This is the most literal mapping in the set: our canary for this IOM plants a real credential in a discoverable file (a `.env`, an issue comment), which is exactly T1552.001's scenario, and using that credential afterwards is T1078 - a stolen-but-valid account/key rather than a novel exploit.",
  },
  {
    iomId: "5",
    framework: "atlas",
    tactic: "AI Attack Staging",
    techniques: [
      { id: "AML.T0054", name: "LLM Jailbreak", url: "https://atlas.mitre.org/techniques/AML.T0054" },
      {
        id: "AML.T0051",
        name: "LLM Prompt Injection",
        url: "https://atlas.mitre.org/techniques/AML.T0051",
      },
    ],
    rationale:
      "This IOM has no honest Enterprise ATT&CK analog - it's the agent's own persona/character being manipulated (or manipulating a human) into acting outside its guardrails, which is squarely what MITRE ATLAS (the ATT&CK-style framework for AI system attacks) models as jailbreaking / prompt injection rather than anything in the classic network-intrusion matrix. Listed here for completeness; verify technique IDs against the live ATLAS matrix before citing in a final report, since ATLAS is newer and evolves faster than Enterprise ATT&CK.",
  },
  {
    iomId: "6",
    framework: "attack",
    tactic: "Lateral Movement",
    techniques: [
      {
        id: "T1210",
        name: "Exploitation of Remote Services",
        url: "https://attack.mitre.org/techniques/T1210/",
      },
    ],
    rationale:
      "Once the agent has some foothold, actually exploiting another host it finds on the internal network to gain further access is classic lateral movement via service exploitation.",
  },
  {
    iomId: "7",
    framework: "attack",
    tactic: "Discovery",
    techniques: [
      {
        id: "T1046",
        name: "Network Service Discovery",
        url: "https://attack.mitre.org/techniques/T1046/",
      },
      {
        id: "T1018",
        name: "Remote System Discovery",
        url: "https://attack.mitre.org/techniques/T1018/",
      },
    ],
    rationale:
      "Scanning or mapping the internal network without exploiting anything - the reconnaissance-after-foothold step ATT&CK separates out as Discovery, distinct from IOM 6's actual exploitation.",
  },
  {
    iomId: "8",
    framework: "attack",
    tactic: "Command and Control / Exfiltration",
    techniques: [
      {
        id: "T1071",
        name: "Application Layer Protocol",
        url: "https://attack.mitre.org/techniques/T1071/",
      },
      {
        id: "T1567",
        name: "Exfiltration Over Web Service",
        url: "https://attack.mitre.org/techniques/T1567/",
      },
    ],
    rationale:
      "The IOM itself is just the boundary violation (the agent reaching the open internet when its task required it to stay sandboxed) - what it's mapped to is whatever that access is actually used for, most often standard C2/exfiltration channels over ordinary web protocols.",
  },
];

export const MITRE_MAPPING_BY_IOM = new Map(MITRE_MAPPING.map((m) => [m.iomId, m]));
