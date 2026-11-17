"""Embedding-based selection of award and request sentences."""

import json
import math
import re
from functools import lru_cache, partial
from itertools import batched

from ..extraction.source.text import MONEY, REASONS, sentence_fragments
from .encoding import create_embeddings, validate_settings as validate_encoder_settings

TARGET_CLASSES = ("judgment", "request")
EXCLUDED_CLASSES = ("prior_payment", "procedural_costs", "mixed", "other_payments")
PATTERN_CLASSES = TARGET_CLASSES + EXCLUDED_CLASSES + ("judgment-denial",)


def validate_settings(settings, patterns):
    """
    Validate embedding settings, keyword groups and pattern classes before model loading.

    args:
        settings: Embedding model, runtime settings and similarity threshold.
        patterns: Nonempty target and exclusion phrase lists.

    returns:
        None.
    """
    required = {
        "model",
        "revision",
        "device",
        "batch_size",
        "max_length",
        "minimum_cosine_similarity",
        "candidate_keywords",
    }
    if not isinstance(settings, dict) or set(settings) != required:
        raise ValueError(f"targets.yaml embedding requires {sorted(required)}")
    validate_encoder_settings(settings)
    threshold = settings["minimum_cosine_similarity"]
    if (
        type(threshold) not in (int, float)
        or not math.isfinite(threshold)
        or not 0 <= threshold <= 1
    ):
        raise ValueError("minimum_cosine_similarity must be between 0 and 1")
    keywords = settings["candidate_keywords"]
    # Denial screening uses every sentence, so it has no keyword group.
    keyword_groups = {*TARGET_CLASSES, *EXCLUDED_CLASSES, "shared"}
    if not isinstance(keywords, dict) or set(keywords) != keyword_groups:
        raise ValueError(
            f"candidate_keywords requires {sorted(keyword_groups)} groups"
        )
    if not any(keywords.values()) or any(
        not isinstance(words, list)
        or any(not isinstance(word, str) or not word.strip() for word in words)
        for words in keywords.values()
    ):
        raise ValueError(
            "candidate_keywords groups must contain word stems, with at least one nonempty group"
        )
    if not isinstance(patterns, dict) or set(patterns) != set(PATTERN_CLASSES):
        raise ValueError(f"targets.yaml patterns requires {list(PATTERN_CLASSES)} lists")
    for label, phrases in patterns.items():
        if (
            not isinstance(phrases, list)
            or not phrases
            or any(not isinstance(p, str) or not p.strip() for p in phrases)
        ):
            raise ValueError(f"Target patterns for {label} must be nonempty strings")
        for phrase in phrases:
            prepare_text(phrase)


def candidate_sentences(text, keywords):
    """Locate each PLN amount with five words of context and preserved source evidence.

    args:
        text: Full normalized judgment text.
        keywords: Configured stems admitting monetary source clauses.

    returns:
        Independently classified amount windows, exact offsets and operative context.
    """
    core = {
        label: re.compile(r"\b(?:" + "|".join(re.escape(word) for word in words) + r")\w*", re.I)
        if words else re.compile(r"(?!)")
        for label, words in keywords.items()
    }
    reasons = REASONS.search(text)
    result = []
    for line in re.finditer(r"[^\n]+", text):
        for sentence in sentence_fragments({"text": line[0], "start": line.start(), "end": line.end()}):
            for clause in re.finditer(r"[^;]+;?", sentence["text"]):
                source = clause[0].strip()
                offset = sentence["start"] + clause.start() + len(clause[0]) - len(clause[0].lstrip())
                if not any(pattern.search(source) for pattern in core.values()):
                    continue
                classes = tuple(label for label in TARGET_CLASSES if label in core and core[label].search(source))
                if not classes and core["shared"].search(source):
                    classes = TARGET_CLASSES
                classes += tuple(label for label in EXCLUDED_CLASSES if label in core and core[label].search(source))
                judicial = bool(re.search(r"\b(?:zasądz\w*|przyzn\w*|nakaz\w*|zobowiąz\w*|orzek\w*|orzecz\w*|nakład\w*)", source, re.I))
                operative = (reasons is None or offset < reasons.start()) and bool(re.search(r"\b(?:zasądza|przyznaje|nakazuje|zobowiązuje|orzeka|nakłada)\b", source, re.I)) and not re.search(r"\b(?:wnosi|wniósł|żąda|domaga)\b", source, re.I)
                amounts = list(MONEY.finditer(source))
                for index, amount in enumerate(amounts):
                    before = list(re.finditer(r"\S+", source[:amount.start()]))
                    after = list(re.finditer(r"\S+", source[amount.end():]))
                    start = before[-5].start() if len(before) >= 5 else 0
                    end = amount.end() + after[4].end() if len(after) >= 5 else len(source)
                    window = source[start:end]
                    local_classes = classes
                    costs = bool(re.search(r"koszt\w*\s+(?:proces|postępow|zastępstw|sądow)|zastępstw\w*\s+proces|opłat\w*\s+sądow|wynagrodzeni\w*\s+pełnomocn|Skarbu Państwa|wynagrodzenie.*biegł", source[amount.start():amounts[index+1].start()] if amount is not amounts[-1] else source[amount.start():], re.I))
                    costs = costs or bool(re.search(r"nakazuje\s+(?:ściągnąć|pobrać)|(?:poniesion|wyłożon)\w*.*Skarb|przez Skarb Państwa|na rzecz Skarbu Państwa|tytułem opłat", source, re.I))
                    costs = costs or bool(re.search(r"(?:potrąc|rozlicz)\w*.*koszt|wzajemn\w*.*(?:potrąc|rozlicz)", source, re.I))
                    costs = costs or bool(re.search(r"pełnomocnik|biegł|koszt\w*\s+(?:proces|postępow|sądow)|zastępstw\w*\s+proces|opłat\w*\s+sądow", source[max(0, amount.start()-100):amount.start()], re.I))
                    if operative and amount is amounts[0] and not costs:
                        local_classes = tuple(label for label in local_classes if label != "prior_payment" and (label != "other_payments" or not re.search(r"\bz\s+(?:ustawowymi\s+)?odsetkami", source, re.I)))
                    if not judicial or costs or (operative and amount is not amounts[0]):
                        local_classes = tuple(label for label in local_classes if label != "judgment")
                    if costs and "procedural_costs" not in local_classes:
                        local_classes += ("procedural_costs",)
                    if "prior_payment" in local_classes and not re.search(r"wypłac|zapłac|otrzyma|likwidac|dotychczas\s+(?:wypłac|przyzna)", window, re.I):
                        local_classes = tuple(label for label in local_classes if label != "prior_payment")
                    if not local_classes:
                        local_classes = EXCLUDED_CLASSES
                    result.append({
                        "text": text[offset+start:offset+end], "start": offset+start, "end": offset+end,
                        "amount_start": offset+amount.start(), "amount_end": offset+amount.end(),
                        "sentence": {"text": source, "start": offset, "end": offset+len(source)},
                        "classes": local_classes, "operative": bool(operative),
                        "first_amount": amount is amounts[0], "procedural": costs,
                    })
    return result


def explicit_denial(text):
    """Require complete dismissal and reject partial, appellate or party-request wording.

    args:
        text: Complete source sentence.

    returns:
        True only for an explicit unqualified dismissal or complete refusal of payment.
    """
    if re.search(r"apelac|kasac|w pozostał|w części|częściow|co do kwoty|ponad kwot|wn(?:osi|iósł)|domaga|żąda|zażąda|nie\s+oddal|nie\s+odmaw|zasądza|zasądził", text, re.I):
        return False
    return bool(re.search(
        r"\boddal(?:a|ił|iła|ono|eniu|enie)\b.*?\b(?:powództw|żądani|roszczeni)\w*"
        r"|\b(?:powództw|żądani|roszczeni)\w*.*?\boddal(?:a|ił|iła|ono|eniu|enie)\b"
        r"|\bodmawia\b.*?\b(?:jakiejkolwiek|jakimkolwiek|całości)\b", text, re.I,
    ))


def prepare_text(text):
    """
    Neutralize example amounts and replace template slots with Polish role words.

    args:
        text: Pattern template or original source sentence.

    returns:
        Text used only for embedding; the original source remains unchanged.
    """
    replacements = {
        "defendant": "pozwanego",
        "claimant": "powoda",
        "amount": "100 zł",
        "previous_amount": "100 zł",
        "additional_amount": "100 zł",
    }
    for key in re.findall(r"\{([^{}]+)\}", text):
        if key not in replacements:
            raise ValueError(f"Unknown target-pattern placeholder: {key}")
        text = text.replace("{" + key + "}", replacements[key])
    text = re.sub(r"^\s*(?:\d+[.)]|[IVXLCDM]+[.)])\s*", "", text, flags=re.I)
    text = MONEY.sub("100 zł", text)
    text = re.sub(r"(100 zł)\s*\((?=(?:jed|dwa|dwie|dwudzi|trz|czter|pię|sze|sied|osiem|dziew|sto|tysi|mil))[^)]*(?:\)|$)", r"\1", text, flags=re.I)
    text = re.sub(r"\b(?:(powoda|powódki|powodów|pozwanego|pozwanej|pokrzywdzonego|pokrzywdzonej)\s+)?(?:[A-ZĄĆĘŁŃÓŚŹŻ]\.\s*){2,}(?:\(\s*(?:\d+|[A-ZĄĆĘŁŃÓŚŹŻ]\.)\s*\))?", lambda match: (match[1] or "powoda") + " ", text)
    text = text.replace("(...)", " ")
    return re.sub(r"\s+", " ", text).strip().rstrip(".,;:")


class TargetMatcher:
    """Cache pattern embeddings and rank source sentences by cosine similarity."""

    def __init__(self, settings, patterns, encoder=None):
        """
        Encode pattern templates once for reuse across judgments.

        args:
            settings: Embedding configuration and minimum similarity.
            patterns: Target and exclusion templates.
            encoder: Optional existing sentence encoder.

        returns:
            None.
        """
        validate_settings(settings, patterns)
        self.settings = settings
        self.patterns = [
            (label, phrase) for label, phrases in patterns.items() for phrase in phrases
        ]
        self.encode = encoder.encode if encoder is not None else partial(
            create_embeddings, settings=settings
        )
        self.pattern_vectors = self.encode(
            [prepare_text(phrase) for _, phrase in self.patterns]
        )

    def match_denial(self, text):
        """Check full sentences for denial before any monetary candidate selection.

        args:
            text: Full normalized judgment, including sentences without PLN or keywords.

        returns:
            Strongest explicit denial across all source batches, or None.
        """
        from .cosine_similarity import cosine_similarity

        indices = [
            index for index, (label, _) in enumerate(self.patterns)
            if label == "judgment-denial"
        ]
        costs = [
            index for index, (label, _) in enumerate(self.patterns)
            if label == "procedural_costs"
        ]
        sentences = (
            sentence
            for line in re.finditer(r"[^\n]+", text)
            for sentence in sentence_fragments({"text": line[0], "start": line.start(), "end": line.end()})
            if explicit_denial(sentence["text"])
        )
        result = None
        for batch in batched(sentences, self.settings["batch_size"]):
            vectors = self.encode([prepare_text(row["text"]) for row in batch])
            scores = cosine_similarity(vectors, self.pattern_vectors[indices + costs], device=self.settings["device"]).cpu()
            values, patterns = scores[:, :len(indices)].max(dim=1)
            cost_values = scores[:, len(indices):].max(dim=1).values
            values = values.masked_fill(values <= cost_values, -1)
            best = int(values.argmax())
            score = float(values[best])
            if score > self.settings["minimum_cosine_similarity"] and (result is None or score > result["similarity"]):
                result = {**batch[best], "similarity": score, "pattern": self.patterns[indices[int(patterns[best])]][1]}
        return result

    def match(self, text):
        """
        Classify monetary windows against non-target roles before ranking judgment matches.

        args:
            text: Full normalized judgment text.

        returns:
            Best matches per target/exclusion class, with source offsets and scores.
        """
        from .cosine_similarity import cosine_similarity

        sentences = candidate_sentences(text, self.settings["candidate_keywords"])
        result = dict.fromkeys(PATTERN_CLASSES)
        if not sentences:
            return result
        vectors = self.encode([prepare_text(row["text"]) for row in sentences])
        scores = cosine_similarity(
            vectors, self.pattern_vectors, device=self.settings["device"]
        ).cpu()
        judgments = []
        assigned = {}
        for row, similarities in zip(sentences, scores, strict=True):
            best = {}
            for index, (label, phrase) in enumerate(self.patterns):
                if label not in row["classes"]:
                    continue
                score = float(similarities[index])
                if label not in best or score > best[label][0]:
                    best[label] = (score, phrase)
            exclusions = [label for label in (*EXCLUDED_CLASSES, "request") if label in best and best[label][0] > self.settings["minimum_cosine_similarity"]]
            eligible = exclusions or [label for label in ("judgment",) if label in best]
            if not eligible:
                continue
            label = max(eligible, key=lambda key: (best[key][0], key in EXCLUDED_CLASSES))
            score, phrase = best[label]
            if score <= self.settings["minimum_cosine_similarity"]:
                continue
            selected = {**row, "similarity": score, "pattern": phrase}
            assigned[row["amount_start"]] = label
            if label == "judgment":
                judgments.append(selected)
            previous = result[label]
            if previous is None or (label == "judgment" and (row["operative"], score) > (previous["operative"], previous["similarity"])) or (label != "judgment" and score > previous["similarity"]):
                result[label] = selected
        principal = [row for row in sentences if row["operative"] and row["first_amount"] and not row["procedural"] and "judgment" in row["classes"] and assigned.get(row["amount_start"]) not in (*EXCLUDED_CLASSES, "request")]
        operative = [row for row in judgments if row["operative"] and row["first_amount"]]
        if principal and any(assigned.get(row["amount_start"]) != "judgment" for row in principal):
            result["judgment"] = None
        elif operative:
            result["judgment"] = {**max(operative, key=lambda row: row["similarity"]), "awards": operative}

        return result


@lru_cache(maxsize=1)
def cached_matcher(settings_json, patterns_json):
    """
    Reuse one model and pattern matrix for an unchanged configuration.

    args:
        settings_json: Serialized embedding configuration.
        patterns_json: Serialized pattern lists.

    returns:
        Initialized target matcher.
    """
    return TargetMatcher(json.loads(settings_json), json.loads(patterns_json))


def match_targets(text, config):
    """
    Locate denial evidence before monetary target and exclusion contexts.

    args:
        text: Full normalized judgment.
        config: Effective pipeline configuration.

    returns:
        Denial evidence, or best monetary matches per target/exclusion class.
    """
    if not text.strip():
        return dict.fromkeys(PATTERN_CLASSES)
    reasons = REASONS.search(text)
    ruling = text[:reasons.start()] if reasons else text
    if re.search(r"oddal\w*\s+apelac|apelac\w*.*oddal|utrzym\w*.*w mocy", ruling, re.I):
        principal = [row for row in candidate_sentences(ruling, config["embedding"]["candidate_keywords"]) if row["operative"] and row["first_amount"] and not row["procedural"] and "judgment" in row["classes"]]
        if not principal:
            return {**dict.fromkeys(PATTERN_CLASSES), "excluded_reason": "appeal contains no new principal award"}
    matcher = cached_matcher(
        json.dumps(config["embedding"], sort_keys=True),
        json.dumps(config["target_patterns"], sort_keys=True),
    )
    result = matcher.match(text)
    selected = result["judgment"]
    if selected is not None and selected.get("operative"):
        return result
    reasons = REASONS.search(text)
    denial = matcher.match_denial(text[:reasons.start()] if reasons and reasons.start() else text)
    if denial is not None:
        result.update(judgment=None, **{"judgment-denial": denial})
    return result
