#!/usr/bin/env python3
"""
Rule-Based Interactive Terminal Chatbot / Assistant
===================================================
A responsible, multi-intent conversational assistant built for customer support
and product FAQs.

Key Capabilities:
1. Multi-Intent Recognition: Identifies compound queries (e.g. greeting + multiple FAQs).
2. Regex & Keyword Matching: Normalizes text and scores intent confidence.
3. Conversational State Management: Tracks conversation lifecycle, user name, and context.
4. Responsible AI Guardrails: Ethical disclaimer, safety filters, and human escalation.
5. Contextual Follow-ups: Resolves queries relying on prior conversational context.
6. Graceful Fallbacks: Multi-tiered confidence thresholding with suggestion prompts.
7. Clean Exit Handling: Graceful exit commands ('bye', 'exit', 'quit', etc.).
"""

import os
import sys
import json
import re
from enum import Enum, auto
from typing import List, Dict, Optional, Tuple, Set, Any
from dataclasses import dataclass, field


# ============================================================================
# Color & Formatting Utilities (Graceful ANSI / Plaintext Fallback)
# ============================================================================
class Style:
    """Terminal styling codes with auto-detection for non-ANSI environments."""
    USE_COLOR = sys.stdout.isatty() and os.name != "nt" or "WT_SESSION" in os.environ or "TERM" in os.environ

    CYAN = "\033[96m" if USE_COLOR else ""
    GREEN = "\033[92m" if USE_COLOR else ""
    YELLOW = "\033[93m" if USE_COLOR else ""
    BLUE = "\033[94m" if USE_COLOR else ""
    MAGENTA = "\033[95m" if USE_COLOR else ""
    RED = "\033[91m" if USE_COLOR else ""
    BOLD = "\033[1m" if USE_COLOR else ""
    DIM = "\033[2m" if USE_COLOR else ""
    RESET = "\033[0m" if USE_COLOR else ""

    @classmethod
    def disable_colors(cls):
        cls.CYAN = ""
        cls.GREEN = ""
        cls.YELLOW = ""
        cls.BLUE = ""
        cls.MAGENTA = ""
        cls.RED = ""
        cls.BOLD = ""
        cls.DIM = ""
        cls.RESET = ""


# ============================================================================
# Conversational State Management
# ============================================================================
class ConversationState(Enum):
    """Lifecycle states of the conversational assistant."""
    GREETING = auto()               # Initial welcoming state
    AWAITING_QUERY = auto()         # Active, ready for questions
    INTENT_IDENTIFICATION = auto()  # Processing recognized intent(s)
    RESOLUTION = auto()             # Provided answer, ready for follow-up
    CLARIFICATION = auto()          # Asking for clarification on low confidence
    EXIT = auto()                   # Clean termination state


@dataclass
class TurnRecord:
    """Represents a single conversational turn."""
    user_input: str
    detected_intents: List[str]
    bot_response: str
    state_before: ConversationState
    state_after: ConversationState


@dataclass
class ConversationContext:
    """Maintains state memory across multiple conversational turns."""
    current_state: ConversationState = ConversationState.GREETING
    user_name: Optional[str] = None
    last_topic: Optional[str] = None
    consecutive_fallbacks: int = 0
    history: List[TurnRecord] = field(default_factory=list)
    pending_clarification_options: List[Tuple[str, str]] = field(default_factory=list)

    def record_turn(self, user_input: str, intents: List[str], response: str, next_state: ConversationState):
        record = TurnRecord(
            user_input=user_input,
            detected_intents=intents,
            bot_response=response,
            state_before=self.current_state,
            state_after=next_state
        )
        self.history.append(record)
        self.current_state = next_state


# ============================================================================
# Intent Data Structures
# ============================================================================
@dataclass
class RecognizedIntent:
    """Result of an intent evaluation."""
    intent_id: str
    confidence: float
    title: str
    response: str
    matched_clause: str
    is_primary: bool = True


# ============================================================================
# Text Normalization & Preprocessing
# ============================================================================
class TextNormalizer:
    """Normalizes input text, expands contractions, and strips noise."""

    CONTRACTIONS = {
        r"\bcan't\b": "cannot",
        r"\bwon't\b": "will not",
        r"\bi'm\b": "i am",
        r"\bi've\b": "i have",
        r"\bi'll\b": "i will",
        r"\bi'd\b": "i would",
        r"\bwhat's\b": "what is",
        r"\bwhere's\b": "where is",
        r"\bhow's\b": "how is",
        r"\bwhen's\b": "when is",
        r"\bwho's\b": "who is",
        r"\bthat's\b": "that is",
        r"\bthere's\b": "there is",
        r"\bit's\b": "it is",
        r"\bdon't\b": "do not",
        r"\bdoesn't\b": "does not",
        r"\bdidn't\b": "did not",
        r"\byou're\b": "you are",
        r"\byou've\b": "you have",
        r"\byou'll\b": "you will",
        r"\bwe're\b": "we are",
        r"\bthey're\b": "they are",
        r"\bplz\b": "please",
        r"\bu\b": "you",
        r"\bur\b": "your",
        r"\br\b": "are"
    }

    STOP_WORDS = {
        "a", "an", "the", "is", "am", "are", "was", "were", "be", "been", "being",
        "do", "does", "did", "have", "has", "had", "to", "for", "in", "on", "at",
        "of", "by", "with", "about", "my", "your", "his", "her", "their", "our",
        "me", "you", "him", "them", "us", "i", "it", "this", "that", "can", "could",
        "would", "should", "tell", "know", "wondering", "like", "want"
    }

    @classmethod
    def expand_contractions(cls, text: str) -> str:
        for pattern, replacement in cls.CONTRACTIONS.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text

    @classmethod
    def normalize(cls, text: str) -> str:
        """Lowercases, expands contractions, strips excess whitespace."""
        text = text.lower().strip()
        text = cls.expand_contractions(text)
        # Collapse multiple spaces
        text = re.sub(r"\s+", " ", text)
        return text

    @classmethod
    def tokenize(cls, text: str) -> List[str]:
        """Extract alphanumeric words from text."""
        normalized = cls.normalize(text)
        return re.findall(r"\b[a-z0-9]+\b", normalized)

    @classmethod
    def extract_significant_keywords(cls, text: str) -> Set[str]:
        """Extract meaningful keywords filtering out conversational stop words."""
        tokens = cls.tokenize(text)
        return {token for token in tokens if token not in cls.STOP_WORDS}

    @classmethod
    def split_into_clauses(cls, text: str) -> List[str]:
        """
        Splits a compound user sentence into distinct logical clauses for
        multi-intent recognition. Handles punctuation breaks and coordinating conjunctions.
        """
        # First split on punctuation sentence boundaries (. , ? ! ; :)
        initial_chunks = re.split(r"[.?!;:,\n]+", text)

        clauses = []
        for chunk in initial_chunks:
            chunk = chunk.strip()
            if not chunk:
                continue

            # Split on coordinating conjunctions if the clause is compound
            # e.g., "what are your hours and how do I submit my project"
            sub_clauses = re.split(
                r"\b(?:and\s+also|and\s+then|and|also|plus|additionally|as\s+well\s+as|along\s+with)\b",
                chunk,
                flags=re.IGNORECASE
            )
            for sc in sub_clauses:
                clean_sc = sc.strip()
                if clean_sc:
                    clauses.append(clean_sc)

        return clauses if clauses else [text]


# ============================================================================
# Knowledge Base & Rule Matching Engine
# ============================================================================
class KnowledgeBase:
    """Manages greetings, business hours, FAQ items, and intent rules."""

    DEFAULT_GREETINGS = [
        "hello", "hi", "hey", "good morning", "good afternoon",
        "good evening", "greetings", "howdy", "hiya"
    ]

    DEFAULT_FAQS = [
        {
            "id": "hours_of_operation",
            "topic": "hours",
            "question": "What are your hours of operation?",
            "answer": "We operate Monday through Friday from 9:00 AM to 6:00 PM IST.",
            "keywords": ["hours", "operation", "time", "timing", "timings", "open", "close", "schedule", "working", "business"],
            "regex": [
                r"\b(hours?|timing?s?|schedule)\b.*\b(operation|working|business|office|support)?\b",
                r"\b(when|what\s+time)\b.*\b(open|close|operate|work)\b",
                r"\b(are\s+you\s+open|operating\s+hours|business\s+hours)\b"
            ]
        },
        {
            "id": "internship_project_submission",
            "topic": "submission",
            "question": "How do I submit my internship project?",
            "answer": "You can submit your public GitHub repository link through your Student Workspace.",
            "keywords": ["submit", "submission", "internship", "project", "github", "workspace", "repo", "repository", "link", "upload"],
            "regex": [
                r"\b(how|where)\b.*\b(submit|send|upload|turn\s+in)\b.*\b(project|internship|assignment|work|code)\b",
                r"\b(internship\s+project|project\s+submission|submit\s+my\s+project|github\s+link)\b",
                r"\bhow\s+do\s+i\s+submit\b"
            ]
        },
        {
            "id": "certificate_issuance",
            "topic": "certificate",
            "question": "When will I receive my certificate?",
            "answer": "Certificates are reviewed and issued within 3-5 business days after your code review.",
            "keywords": ["certificate", "certificates", "receive", "issued", "issue", "reviewed", "code review", "completion", "cert", "lor"],
            "regex": [
                r"\b(when|how\s+long)\b.*\b(receive|get|issued?|arrive|ready|deliver)\b.*\b(certificate|cert|certification|lor)\b",
                r"\b(receive|get)\s+my\s+certificate\b",
                r"\b(certificate\s+issuance|completion\s+certificate|certificate\s+status)\b"
            ]
        }
    ]

    def __init__(self, faq_file_path: Optional[str] = None):
        self.greetings: List[str] = list(self.DEFAULT_GREETINGS)
        self.faqs: List[Dict[str, Any]] = list(self.DEFAULT_FAQS)
        self.faq_source: str = "built-in defaults"

        if faq_file_path:
            self.load_from_json(faq_file_path)
        else:
            # Check default locations
            candidate_paths = [
                "sample_faq.json",
                os.path.join(os.path.dirname(__file__), "sample_faq.json"),
                os.path.join(os.path.dirname(__file__), "..", "sample_faq.json"),
                r"c:\Users\KRYVEN BLAZE\Downloads\sample_faq.json"
            ]
            for path in candidate_paths:
                if os.path.exists(path):
                    self.load_from_json(path)
                    break

    def load_from_json(self, file_path: str):
        """Loads and indexes questions from a JSON dataset."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "greetings" in data and isinstance(data["greetings"], list):
                self.greetings = [g.strip().lower() for g in data["greetings"] if g.strip()]

            if "faqs" in data and isinstance(data["faqs"], list):
                loaded_faqs = []
                for idx, item in enumerate(data["faqs"]):
                    q = item.get("question", "").strip()
                    a = item.get("answer", "").strip()
                    if not q or not a:
                        continue

                    # Generate automatic keywords and regex patterns for dynamic FAQs
                    topic = self._infer_topic(q)
                    if topic == "hours":
                        faq_id = "hours_of_operation"
                    elif topic == "submission":
                        faq_id = "internship_project_submission"
                    elif topic == "certificate":
                        faq_id = "certificate_issuance"
                    else:
                        faq_id = f"custom_faq_{idx+1}"
                    keywords = list(TextNormalizer.extract_significant_keywords(q))

                    # Check if this matches one of our known defaults to enrich with robust regex
                    enriched_regex = self._generate_regex_for_question(q)

                    loaded_faqs.append({
                        "id": faq_id,
                        "topic": topic,
                        "question": q,
                        "answer": a,
                        "keywords": keywords,
                        "regex": enriched_regex
                    })

                if loaded_faqs:
                    self.faqs = loaded_faqs
                    self.faq_source = os.path.abspath(file_path)
        except Exception as e:
            # Fallback to defaults if reading failed
            self.faq_source = f"built-in defaults (failed loading {file_path}: {e})"

    def _infer_topic(self, question: str) -> str:
        q_lower = question.lower()
        if "hour" in q_lower or "operation" in q_lower or "timing" in q_lower:
            return "hours"
        elif "submit" in q_lower or "project" in q_lower or "workspace" in q_lower:
            return "submission"
        elif "certificate" in q_lower or "cert" in q_lower:
            return "certificate"
        return "general"

    def _generate_regex_for_question(self, question: str) -> List[str]:
        q_lower = question.lower()
        patterns = []

        if "hour" in q_lower or "operation" in q_lower:
            patterns.extend([
                r"\b(hours?|timings?|schedule)\b",
                r"\b(open|close|operating|business\s+hours)\b",
                r"\bwhen\s+are\s+you\s+open\b"
            ])
        elif "submit" in q_lower and ("project" in q_lower or "internship" in q_lower):
            patterns.extend([
                r"\b(submit|submission|upload|turn\s+in)\b.*\b(project|internship|assignment|repo|github)\b",
                r"\bhow\s+(do\s+i|to)\s+submit\b",
                r"\bproject\s+submission\b"
            ])
        elif "certificate" in q_lower:
            patterns.extend([
                r"\b(certificate|cert|certification)\b",
                r"\b(receive|get|issued?)\b.*\b(certificate|cert)\b",
                r"\bwhen\s+will\s+i\s+receive\b"
            ])
        else:
            # Generic pattern from keywords
            keywords = list(TextNormalizer.extract_significant_keywords(question))
            if len(keywords) >= 2:
                joined = "|".join(re.escape(k) for k in keywords[:4])
                patterns.append(rf"\b({joined})\b")

        return patterns


# ============================================================================
# Rule-Based Intent Recognizer (with Multi-Intent Support)
# ============================================================================
class IntentRecognizer:
    """
    Parses user input using keyword matching, regular expressions, and clause
    segmentation to recognize multiple intents in a single utterance.
    """

    EXIT_REGEX = [
        r"^\s*(bye|goodbye|exit|quit|cya|see\s+ya|farewell|close|end|stop|terminate)\s*$",
        r"\b(bye|goodbye|see\s+you\s+later|have\s+a\s+good\s+day)\b",
        r"^(q|:q)$"
    ]

    GRATITUDE_REGEX = [
        r"\b(thanks?|thank\s+you|appreciate\s+it|grateful|kudos|much\s+appreciated)\b"
    ]

    HELP_REGEX = [
        r"\b(help|options|menu|commands|what\s+can\s+you\s+do|what\s+do\s+you\s+know|topics)\b"
    ]

    HUMAN_ESCALATION_REGEX = [
        r"\b(speak\s+to\s+a\s+human|talk\s+to\s+a\s+person|human\s+agent|real\s+person|customer\s+representative|support\s+agent|contact\s+support)\b"
    ]

    NAME_REGEX = [
        r"\b(?:my\s+name\s+is|i\s+am|i'm|call\s+me)\s+([a-zA-Z]{2,20})\b"
    ]

    BOT_IDENTITY_REGEX = [
        r"\b(who\s+are\s+you|what\s+are\s+you|are\s+you\s+(a\s+bot|a\s+human|ai|robot)|tell\s+me\s+about\s+yourself)\b"
    ]

    SENSITIVE_DATA_REGEX = [
        r"\b(?:\d[ -]*?){13,16}\b",              # Potential Credit Card
        r"\b\d{3}-\d{2}-\d{4}\b",               # SSN
        r"\b(password|pin|secret|cvv)\s*[:=]\s*\S+\b" # Passwords / PINs
    ]

    INAPPROPRIATE_REGEX = [
        r"\b(stupid|idiot|dumb|hate\s+you|shut\s+up|garbage|trash|useless)\b"
    ]

    def __init__(self, kb: KnowledgeBase):
        self.kb = kb

    def check_sensitive_data(self, text: str) -> bool:
        """Responsible AI filter: Detect potential sensitive data leakage."""
        for pattern in self.SENSITIVE_DATA_REGEX:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def check_inappropriate(self, text: str) -> bool:
        """Responsible AI filter: Detect abusive or toxic inputs."""
        for pattern in self.INAPPROPRIATE_REGEX:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def extract_name(self, text: str) -> Optional[str]:
        """Extracts user's name if introduced."""
        for pattern in self.NAME_REGEX:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip().capitalize()
                # Exclude obvious non-names
                if name.lower() not in {"here", "there", "ready", "interested", "looking", "asking", "confused"}:
                    return name
        return None

    def match_exit(self, clause: str) -> bool:
        for pattern in self.EXIT_REGEX:
            if re.search(pattern, clause, re.IGNORECASE):
                return True
        return False

    def match_greeting(self, clause: str) -> bool:
        norm = TextNormalizer.normalize(clause)
        # Direct match against greetings list
        for g in self.kb.greetings:
            if re.search(rf"\b{re.escape(g)}\b", norm):
                return True
        return False

    def match_gratitude(self, clause: str) -> bool:
        for pattern in self.GRATITUDE_REGEX:
            if re.search(pattern, clause, re.IGNORECASE):
                return True
        return False

    def match_help(self, clause: str) -> bool:
        for pattern in self.HELP_REGEX:
            if re.search(pattern, clause, re.IGNORECASE):
                return True
        return False

    def match_human_escalation(self, clause: str) -> bool:
        for pattern in self.HUMAN_ESCALATION_REGEX:
            if re.search(pattern, clause, re.IGNORECASE):
                return True
        return False

    def match_bot_identity(self, clause: str) -> bool:
        for pattern in self.BOT_IDENTITY_REGEX:
            if re.search(pattern, clause, re.IGNORECASE):
                return True
        return False

    def score_faq_match(self, clause: str, faq: Dict[str, Any]) -> float:
        """
        Calculates a confidence score [0.0, 1.0] for a given FAQ item using:
        1. Regular expression matches (high precision).
        2. Keyword overlap (Jaccard similarity with keyword weighting).
        """
        norm_clause = TextNormalizer.normalize(clause)
        tokens = set(TextNormalizer.tokenize(clause))
        user_keywords = TextNormalizer.extract_significant_keywords(clause)

        # 1. Regex check
        regex_list = faq.get("regex", [])
        for pattern in regex_list:
            if re.search(pattern, norm_clause, re.IGNORECASE):
                return 0.95

        # 2. Keyword check
        faq_keywords = set(faq.get("keywords", []))
        if not faq_keywords:
            faq_keywords = TextNormalizer.extract_significant_keywords(faq.get("question", ""))

        if not faq_keywords:
            return 0.0

        overlap = user_keywords.intersection(faq_keywords)
        if not overlap:
            return 0.0

        # Weighted Jaccard-like score
        overlap_score = len(overlap) / len(faq_keywords)
        precision_score = len(overlap) / max(len(user_keywords), 1)
        combined = (overlap_score * 0.6) + (precision_score * 0.4)

        # Boost if critical question tokens match
        if overlap_score >= 0.5 or len(overlap) >= 2:
            combined = min(0.90, combined + 0.35)

        return min(0.90, combined)

    def match_contextual_follow_up(self, clause: str, last_topic: Optional[str]) -> Optional[RecognizedIntent]:
        """
        Handles context-dependent queries such as:
        - "What about weekends?" -> connects to hours
        - "Where do I find the workspace?" -> connects to submission
        - "How long does the review take?" -> connects to certificate
        """
        if not last_topic:
            return None

        norm = TextNormalizer.normalize(clause)

        if last_topic == "hours":
            if re.search(r"\b(weekend|weekends|saturday|sunday|holiday|holidays|night)\b", norm):
                return RecognizedIntent(
                    intent_id="follow_up_weekend_hours",
                    confidence=0.92,
                    title="Weekend Hours",
                    response="We are closed on weekends (Saturday and Sunday) and national holidays. Support operates strictly Monday to Friday, 9:00 AM to 6:00 PM IST.",
                    matched_clause=clause
                )
            if re.search(r"\b(different\s+time\s+zone|est|pst|utc|gmt)\b", norm):
                return RecognizedIntent(
                    intent_id="follow_up_timezone",
                    confidence=0.88,
                    title="Time Zone Info",
                    response="Our team is based in Indian Standard Time (IST, UTC+5:30). If you are in another timezone, our responses are sent during IST working hours.",
                    matched_clause=clause
                )

        elif last_topic == "submission":
            if re.search(r"\b(private|public|secret)\b", norm):
                return RecognizedIntent(
                    intent_id="follow_up_submission_privacy",
                    confidence=0.92,
                    title="Repository Privacy",
                    response="Please ensure your GitHub repository is set to PUBLIC so that our review mentors can inspect your code and evaluate your project.",
                    matched_clause=clause
                )
            if re.search(r"\b(where\s+is\s+it|link|where\s+to\s+find|student\s+workspace)\b", norm):
                return RecognizedIntent(
                    intent_id="follow_up_workspace_location",
                    confidence=0.90,
                    title="Student Workspace Location",
                    response="You can log in to your Student Workspace at your student portal dashboard using the credentials emailed to you upon enrollment.",
                    matched_clause=clause
                )

        elif last_topic == "certificate":
            if re.search(r"\b(hard\s+copy|physical|print|delivery|mail|courier)\b", norm):
                return RecognizedIntent(
                    intent_id="follow_up_cert_format",
                    confidence=0.91,
                    title="Certificate Format",
                    response="Certificates are delivered digitally as verified PDF credentials with unique verification IDs. Physical copies can be printed from your portal.",
                    matched_clause=clause
                )
            if re.search(r"\b(delay|delayed|not\s+received|late|where\s+is\s+it)\b", norm):
                return RecognizedIntent(
                    intent_id="follow_up_cert_delay",
                    confidence=0.89,
                    title="Certificate Delays",
                    response="If more than 5 business days have passed since your code review was approved, please email support@organization.com with your student ID.",
                    matched_clause=clause
                )

        return None

    def recognize_intents(self, user_input: str, last_topic: Optional[str] = None) -> List[RecognizedIntent]:
        """
        Multi-Intent Recognition Pipeline:
        1. Breaks input into semantic clauses.
        2. Analyzes each clause against rule patterns and FAQ knowledge base.
        3. Identifies all matching intents without duplication.
        4. Ranks and returns recognized intents.
        """
        clauses = TextNormalizer.split_into_clauses(user_input)
        detected_intents: List[RecognizedIntent] = []
        seen_intent_ids: Set[str] = set()

        # Step 1: Check full sentence for contextual follow-up first
        follow_up = self.match_contextual_follow_up(user_input, last_topic)
        if follow_up:
            detected_intents.append(follow_up)
            seen_intent_ids.add(follow_up.intent_id)

        # Step 2: Iterate through individual clauses
        for clause in clauses:
            clean_clause = clause.strip()
            if not clean_clause:
                continue

            # A. Exit Intent
            if self.match_exit(clean_clause):
                if "exit" not in seen_intent_ids:
                    detected_intents.append(RecognizedIntent(
                        intent_id="exit",
                        confidence=1.0,
                        title="Exit",
                        response="Clean exit requested.",
                        matched_clause=clean_clause
                    ))
                    seen_intent_ids.add("exit")
                continue

            # B. Human Escalation Intent
            if self.match_human_escalation(clean_clause):
                if "human_escalation" not in seen_intent_ids:
                    detected_intents.append(RecognizedIntent(
                        intent_id="human_escalation",
                        confidence=0.98,
                        title="Human Support Escalation",
                        response="You can contact a live support representative by emailing support@organization.com or calling +1 (800) 555-0199 Monday-Friday 9 AM - 6 PM IST.",
                        matched_clause=clean_clause
                    ))
                    seen_intent_ids.add("human_escalation")
                continue

            # C. Bot Identity Intent
            if self.match_bot_identity(clean_clause):
                if "bot_identity" not in seen_intent_ids:
                    detected_intents.append(RecognizedIntent(
                        intent_id="bot_identity",
                        confidence=0.95,
                        title="Bot Identity",
                        response="I am an automated rule-based customer support assistant designed to help answer your questions regarding business hours, project submissions, and certificates responsibly.",
                        matched_clause=clean_clause
                    ))
                    seen_intent_ids.add("bot_identity")
                continue

            # D. Help / Menu Intent
            if self.match_help(clean_clause):
                if "help" not in seen_intent_ids:
                    faq_topics = "\n".join([f"  • {faq['question']}" for faq in self.kb.faqs])
                    help_text = (
                        "Here is what I can help you with:\n"
                        f"{faq_topics}\n"
                        "  • Connect with human customer support\n"
                        "  • Type 'bye', 'exit', or 'quit' anytime to leave."
                    )
                    detected_intents.append(RecognizedIntent(
                        intent_id="help",
                        confidence=0.95,
                        title="Help Menu",
                        response=help_text,
                        matched_clause=clean_clause
                    ))
                    seen_intent_ids.add("help")
                continue

            # E. Name Introduction Intent
            name = self.extract_name(clean_clause)
            if name:
                if "name_introduction" not in seen_intent_ids:
                    detected_intents.append(RecognizedIntent(
                        intent_id="name_introduction",
                        confidence=0.95,
                        title="Name Introduction",
                        response=f"Nice to meet you, {name}! How can I help you today?",
                        matched_clause=clean_clause
                    ))
                    seen_intent_ids.add("name_introduction")

            # F. Greeting Intent
            if self.match_greeting(clean_clause):
                if "greeting" not in seen_intent_ids:
                    detected_intents.append(RecognizedIntent(
                        intent_id="greeting",
                        confidence=0.95,
                        title="Greeting",
                        response="Hello! Welcome to our customer support assistant.",
                        matched_clause=clean_clause
                    ))
                    seen_intent_ids.add("greeting")
                # Do not immediately continue: a clause might also contain other words or follow-ups

            # F. Gratitude Intent
            if self.match_gratitude(clean_clause):
                if "gratitude" not in seen_intent_ids:
                    detected_intents.append(RecognizedIntent(
                        intent_id="gratitude",
                        confidence=0.92,
                        title="Gratitude",
                        response="You're very welcome! Happy to assist you.",
                        matched_clause=clean_clause
                    ))
                    seen_intent_ids.add("gratitude")

            # G. FAQ Matching for this clause
            best_faq = None
            best_score = 0.0

            for faq in self.kb.faqs:
                score = self.score_faq_match(clean_clause, faq)
                if score > best_score:
                    best_score = score
                    best_faq = faq

            if best_faq and best_score >= 0.40:
                faq_id = best_faq["id"]
                if faq_id not in seen_intent_ids:
                    detected_intents.append(RecognizedIntent(
                        intent_id=faq_id,
                        confidence=best_score,
                        title=best_faq["question"],
                        response=best_faq["answer"],
                        matched_clause=clean_clause
                    ))
                    seen_intent_ids.add(faq_id)

        # Step 3: Global fallback check if no intents found on clauses
        if not detected_intents:
            # Try full sentence against all FAQs
            best_faq = None
            best_score = 0.0
            for faq in self.kb.faqs:
                score = self.score_faq_match(user_input, faq)
                if score > best_score:
                    best_score = score
                    best_faq = faq

            if best_faq and best_score >= 0.35:
                detected_intents.append(RecognizedIntent(
                    intent_id=best_faq["id"],
                    confidence=best_score,
                    title=best_faq["question"],
                    response=best_faq["answer"],
                    matched_clause=user_input
                ))

        return detected_intents


# ============================================================================
# Conversational Assistant Engine
# ============================================================================
class ConversationalAssistant:
    """
    Coordinates dialog flow, multi-intent synthesis, context tracking,
    responsible AI safeguards, and graceful fallbacks.
    """

    CONFIDENCE_HIGH = 0.65
    CONFIDENCE_MODERATE = 0.35

    def __init__(self, faq_file_path: Optional[str] = None):
        self.kb = KnowledgeBase(faq_file_path)
        self.recognizer = IntentRecognizer(self.kb)
        self.context = ConversationContext()

    def reset(self):
        """Resets the conversation state."""
        self.context = ConversationContext()

    def process_message(self, raw_input: str) -> Tuple[str, bool]:
        """
        Processes a single user turn.
        Returns:
            Tuple[str, bool]: (bot_response_text, should_exit_flag)
        """
        cleaned_input = raw_input.strip()

        # Handle empty input
        if not cleaned_input:
            return "Please type a question or command. You can type 'help' to see what I can do.", False

        # Responsible AI Check 1: Sensitive Data Filter
        if self.recognizer.check_sensitive_data(cleaned_input):
            return (
                "⚠️ [Security Notice] It looks like your message may contain sensitive personal or payment information (such as card numbers or passwords).\n"
                "For your security and privacy, please do not share credentials or sensitive details in this terminal.",
                False
            )

        # Responsible AI Check 2: Content Moderation / Toxicity
        if self.recognizer.check_inappropriate(cleaned_input):
            return (
                "I am committed to providing a respectful and helpful environment. "
                "How can I assist you with your project, business hours, or certificate today?",
                False
            )

        # Name Extraction Check
        extracted_name = self.recognizer.extract_name(cleaned_input)
        if extracted_name and not self.context.user_name:
            self.context.user_name = extracted_name

        # Multi-Intent Recognition
        intents = self.recognizer.recognize_intents(cleaned_input, self.context.last_topic)

        # Check for Clean Exit command
        has_exit = any(i.intent_id == "exit" for i in intents)
        if has_exit:
            farewell = self._generate_exit_response()
            self.context.record_turn(cleaned_input, ["exit"], farewell, ConversationState.EXIT)
            return farewell, True

        # Synthesize multi-intent or fallback response
        response, next_state = self._synthesize_response(intents, cleaned_input)

        # Record turn in conversation history
        intent_ids = [i.intent_id for i in intents]
        self.context.record_turn(cleaned_input, intent_ids, response, next_state)

        return response, False

    def _generate_exit_response(self) -> str:
        name_str = f", {self.context.user_name}" if self.context.user_name else ""
        return f"Thank you for chatting with us{name_str}! Have a great day ahead. Goodbye!"

    def _synthesize_response(self, intents: List[RecognizedIntent], raw_input: str) -> Tuple[str, ConversationState]:
        """
        Synthesizes a response depending on whether zero, one, or multiple intents
        were detected, taking into account confidence tiers.
        """
        # Case A: Low Confidence / Fallback (Zero recognized intents)
        if not intents:
            self.context.consecutive_fallbacks += 1
            return self._generate_fallback_response(raw_input)

        # Reset consecutive fallbacks on successful recognition
        self.context.consecutive_fallbacks = 0

        # Separate Greeting / Gratitude / Informational intents
        greetings = [i for i in intents if i.intent_id == "greeting"]
        gratitudes = [i for i in intents if i.intent_id == "gratitude"]
        info_intents = [i for i in intents if i.intent_id not in ("greeting", "gratitude", "exit")]

        parts = []

        # 1. Prefix with greeting if present
        if greetings:
            name_str = f" {self.context.user_name}" if self.context.user_name else ""
            if not info_intents and not gratitudes:
                return (
                    f"Hello{name_str}! How can I help you today? You can ask about our hours of operation, internship project submissions, or certificates.",
                    ConversationState.AWAITING_QUERY
                )
            else:
                parts.append(f"Hello{name_str}!")

        # 2. Add gratitude acknowledgment if present
        if gratitudes and not info_intents and not greetings:
            name_str = f", {self.context.user_name}" if self.context.user_name else ""
            return (
                f"You're very welcome{name_str}! Let me know if you have any other questions.",
                ConversationState.RESOLUTION
            )

        # 3. Handle informational intents (Single vs. Multi-Intent)
        if len(info_intents) == 1:
            intent = info_intents[0]

            # Update context topic
            self._update_topic_from_intent(intent)

            # Confidence check
            if intent.confidence >= self.CONFIDENCE_HIGH:
                if parts:
                    parts.append(intent.response)
                    return ("\n\n".join(parts), ConversationState.RESOLUTION)
                return (intent.response, ConversationState.RESOLUTION)
            else:
                # Moderate confidence clarification
                clarification = (
                    f"I think you are asking: \"{intent.title}\"\n\n"
                    f"{intent.response}\n\n"
                    "If this did not answer your question, please type 'help' or rephrase your query."
                )
                if parts:
                    parts.append(clarification)
                    return ("\n\n".join(parts), ConversationState.CLARIFICATION)
                return (clarification, ConversationState.CLARIFICATION)

        elif len(info_intents) > 1:
            # Multi-Intent Synthesis: Formats structured answers addressing all questions
            parts.append("I noticed you asked multiple questions. Here are the answers to each:")

            for idx, intent in enumerate(info_intents, 1):
                self._update_topic_from_intent(intent)
                parts.append(f"• {intent.title}\n  {intent.response}")

            parts.append("Feel free to ask if you need further clarification on any of these!")
            return ("\n\n".join(parts), ConversationState.RESOLUTION)

        # Only greetings or gratitudes were present
        if parts:
            return ("\n\n".join(parts), ConversationState.AWAITING_QUERY)

        return self._generate_fallback_response(raw_input)

    def _update_topic_from_intent(self, intent: RecognizedIntent):
        """Keeps track of active topic for contextual follow-up."""
        iid = intent.intent_id.lower()
        if "hour" in iid:
            self.context.last_topic = "hours"
        elif "submission" in iid or "project" in iid:
            self.context.last_topic = "submission"
        elif "cert" in iid:
            self.context.last_topic = "certificate"

    def _generate_fallback_response(self, raw_input: str) -> Tuple[str, ConversationState]:
        """Provides an intelligent, graceful fallback with guidance and escalation."""
        if self.context.consecutive_fallbacks >= 2:
            msg = (
                "I apologize, but I am having trouble understanding your request after a couple of tries.\n"
                "As an automated assistant, my knowledge is currently focused on FAQs.\n\n"
                "Would you like to speak with a human support agent? You can contact us directly:\n"
                "  📧 Email: support@organization.com\n"
                "  📞 Phone: +1 (800) 555-0199 (Mon-Fri 9:00 AM - 6:00 PM IST)\n\n"
                "Or type 'help' to review the questions I can directly answer."
            )
            return msg, ConversationState.CLARIFICATION

        faq_examples = [f"  • \"{f['question']}\"" for f in self.kb.faqs[:3]]
        examples_str = "\n".join(faq_examples)

        msg = (
            "I'm sorry, I couldn't quite understand that. "
            "Could you please rephrase or ask about one of the following topics?\n\n"
            f"{examples_str}\n\n"
            "💡 Tip: You can also type 'help' to see all options, or 'exit' to quit."
        )
        return msg, ConversationState.CLARIFICATION


# ============================================================================
# Interactive Terminal User Interface
# ============================================================================
def print_banner(bot: ConversationalAssistant):
    """Displays a professional welcome banner."""
    faq_count = len(bot.kb.faqs)
    source_name = os.path.basename(bot.kb.faq_source)

    border = "=" * 68
    print(f"{Style.CYAN}{border}")
    print("      RULE-BASED CUSTOMER SUPPORT & PRODUCT ASSISTANT")
    print("         Responsible AI with Multi-Intent Recognition")
    print(f"{border}{Style.RESET}")
    print(f"{Style.DIM}• Knowledge Base: Loaded {faq_count} FAQs ({source_name})")
    print("• Multi-Intent: Ask compound questions (e.g. greeting + hours + certificates)")
    print("• Commands: 'help' for options | 'exit', 'quit', or 'bye' to leave")
    print(f"{border}\n{Style.RESET}")


def run_interactive_loop(faq_path: Optional[str] = None):
    """Main interactive terminal loop."""
    bot = ConversationalAssistant(faq_path)
    print_banner(bot)

    # Initial greeting prompt
    print(f"{Style.GREEN}{Style.BOLD}Assistant > {Style.RESET}Hello! Welcome to Customer Support. How can I assist you today?\n")

    while True:
        try:
            user_input = input(f"{Style.CYAN}{Style.BOLD}You > {Style.RESET}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n\n{Style.YELLOW}Session interrupted. Goodbye!{Style.RESET}")
            break

        if not user_input.strip():
            continue

        response, should_exit = bot.process_message(user_input)

        print(f"\n{Style.GREEN}{Style.BOLD}Assistant > {Style.RESET}{response}\n")

        if should_exit:
            break


# ============================================================================
# Automated Test & Demo Suite
# ============================================================================
def run_test_suite():
    """Runs automated verification tests across all requirements."""
    print(f"\n{Style.BOLD}=== RUNNING AUTOMATED UNIT TESTS ==={Style.RESET}\n")
    bot = ConversationalAssistant()

    test_cases = [
        # 1. Greeting
        ("Hello there!", ["greeting"], False),

        # 2. Business Hours query
        ("What are your hours of operation?", ["hours_of_operation"], False),

        # 3. Project Submission query
        ("How do I submit my internship project?", ["internship_project_submission"], False),

        # 4. Certificate query
        ("When will I receive my certificate?", ["certificate_issuance"], False),

        # 5. Multi-intent: Greeting + Hours + Certificate
        ("Hi, what are your hours and when will I receive my certificate?",
         ["greeting", "hours_of_operation", "certificate_issuance"], False),

        # 6. Multi-intent: Submission + Hours
        ("How do I submit my project and what time are you open?",
         ["internship_project_submission", "hours_of_operation"], False),

        # 7. Contextual follow-up on hours
        ("Are you open on weekends?", ["follow_up_weekend_hours"], False),

        # 8. User Introduction
        ("My name is Sarah", ["name_introduction"], False),

        # 9. Bot Identity
        ("Who are you?", ["bot_identity"], False),

        # 10. Help command
        ("help", ["help"], False),

        # 11. Sensitive data detection
        ("Here is my card 4111-2222-3333-4444", [], False),

        # 12. Fallback on unknown
        ("Tell me how to bake a chocolate cake", [], False),

        # 13. Clean exit
        ("bye", ["exit"], True),
    ]

    passed = 0
    total = len(test_cases)

    for idx, (query, expected_intents, expected_exit) in enumerate(test_cases, 1):
        # Set up state context if testing follow up
        if query == "Are you open on weekends?":
            bot.context.last_topic = "hours"

        response, should_exit = bot.process_message(query)
        detected = bot.context.history[-1].detected_intents if bot.context.history else []

        # Validate exit flag
        exit_ok = (should_exit == expected_exit)

        # Validate expected intents if specified
        if expected_intents:
            intents_ok = all(exp in detected for exp in expected_intents)
        else:
            intents_ok = True

        status = exit_ok and intents_ok
        if status:
            passed += 1
            print(f"  [{Style.GREEN}PASS{Style.RESET}] Test {idx:02d}: \"{query}\"")
        else:
            print(f"  [{Style.RED}FAIL{Style.RESET}] Test {idx:02d}: \"{query}\"")
            print(f"         Expected: {expected_intents}, Exit: {expected_exit}")
            print(f"         Actual:   {detected}, Exit: {should_exit}")

    print(f"\n{Style.BOLD}Test Results: {passed}/{total} Passed.{Style.RESET}\n")
    return passed == total


# ============================================================================
# Command-Line Entry Point
# ============================================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Rule-Based Interactive Terminal Customer Support Assistant with Multi-Intent Recognition."
    )
    parser.add_argument(
        "--faq",
        type=str,
        default=None,
        help="Path to custom FAQ JSON file (default: sample_faq.json)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run non-interactive automated test suite and exit."
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors in terminal output."
    )

    args = parser.parse_args()

    if args.no_color:
        Style.disable_colors()

    if args.test:
        success = run_test_suite()
        sys.exit(0 if success else 1)
    else:
        run_interactive_loop(args.faq)


if __name__ == "__main__":
    main()
