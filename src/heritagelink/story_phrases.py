"""Localized scaffolding for deterministic Story Core generation.

Mirrors :mod:`heritagelink.growth_phrases`: the deterministic path must produce
presentable copy in either language without reaching for a model, so the wording
lives here and the builder only decides which facts fill it.

A blueprint lists the fields a beat *wants*, in priority order.  The builder takes
the first one the product actually has.  Nothing is invented when none are present —
the beat falls back to ``without_fact`` and is booked as artistic licence.
"""

from __future__ import annotations

from dataclasses import dataclass

from heritagelink.story_models import NarrativeTemplate


@dataclass(frozen=True, slots=True)
class BeatBlueprint:
    beat_id: str
    title: str
    intent: str
    emotion: str
    fields: tuple[str, ...]
    with_fact: str
    without_fact: str

    def __post_init__(self) -> None:
        if "{value}" not in self.with_fact:
            raise ValueError(f"blueprint {self.beat_id!r} must interpolate {{value}}")


@dataclass(frozen=True, slots=True)
class StoryPhrases:
    premise: str
    product_fallback: str
    anchor_claim: str
    hedge: str
    artistic_note: str
    attributed_note: str
    templates: dict[NarrativeTemplate, tuple[BeatBlueprint, ...]]
    list_separator: str = ", "

    def blueprints(self, template: NarrativeTemplate) -> tuple[BeatBlueprint, ...]:
        return self.templates[template]


ZH = StoryPhrases(
    premise="一件{product}，把{craft}的手上功夫讲给没见过它的人听。",
    product_fallback="非遗器物",
    anchor_claim="{value}",
    hedge="据手艺人口述，",
    artistic_note="叙事衔接，无事实依据",
    attributed_note="手艺人自述，尚未核实",
    list_separator="、",
    templates={
        NarrativeTemplate.OBJECT_RECORD: (
            BeatBlueprint(
                beat_id="origin",
                title="来处",
                intent="交代这件器物出自哪里",
                emotion="沉静",
                fields=("region", "heritage_item", "craft_name"),
                with_fact="它来自{value}。",
                without_fact="它的来处尚未记录在案。",
            ),
            BeatBlueprint(
                beat_id="material",
                title="材料",
                intent="让观众看见原料本身",
                emotion="专注",
                fields=("materials", "dimensions"),
                with_fact="做它的是{value}。",
                without_fact="用料还没有登记。",
            ),
            BeatBlueprint(
                beat_id="process",
                title="工序",
                intent="展示最费工的那一步",
                emotion="紧张",
                fields=("craft_process", "customization"),
                with_fact="最要紧的一道是{value}。",
                without_fact="工序细节有待手艺人补录。",
            ),
            BeatBlueprint(
                beat_id="today",
                title="今用",
                intent="把器物放回当下的使用场景",
                emotion="舒展",
                fields=("occasion_tags", "recipient_tags"),
                with_fact="今天它出现在{value}。",
                without_fact="它今天的去处，正在被重新找回。",
            ),
        ),
        NarrativeTemplate.ARTISAN_LIFE: (
            BeatBlueprint(
                beat_id="apprentice",
                title="入行",
                intent="交代人和这门手艺的关系",
                emotion="克制",
                fields=("artisan_or_merchant_name", "craft_name"),
                with_fact="{value}，是这双手一生的营生。",
                without_fact="他入行那年的事，没有留下记录。",
            ),
            BeatBlueprint(
                beat_id="craft",
                title="手上功夫",
                intent="用一个动作说明门槛",
                emotion="专注",
                fields=("craft_process", "materials"),
                with_fact="功夫全在{value}上。",
                without_fact="那点门道，暂时还说不清楚。",
            ),
            BeatBlueprint(
                beat_id="turn",
                title="转折",
                intent="说明这门手艺为何一度难以为继",
                emotion="低回",
                fields=("heritage_item", "region"),
                with_fact="{value}，一度只剩下很少的人还在做。",
                without_fact="这门手艺的起落，缺少可查的记载。",
            ),
            BeatBlueprint(
                beat_id="pass_on",
                title="传下去",
                intent="落在今天仍在继续这件事上",
                emotion="平静",
                fields=("customization", "symbolism"),
                with_fact="现在他还在做{value}。",
                without_fact="他还在做，只是没人替他记下来。",
            ),
        ),
        NarrativeTemplate.TIME_DIALOGUE: (
            BeatBlueprint(
                beat_id="museum",
                title="馆藏",
                intent="从一件可查的旧物起头",
                emotion="肃穆",
                fields=("heritage_item", "cultural_background"),
                with_fact="馆里那件是{value}。",
                without_fact="对照的旧物暂时没有找到出处。",
            ),
            BeatBlueprint(
                beat_id="pattern",
                title="纹样",
                intent="把旧物身上的符号说清楚",
                emotion="好奇",
                fields=("symbolism", "meaning_tags"),
                with_fact="它身上的纹样讲的是{value}。",
                without_fact="纹样的含义还没有可靠的解释。",
            ),
            BeatBlueprint(
                beat_id="remake",
                title="复刻",
                intent="展示当代这一件如何回应它",
                emotion="紧张",
                fields=("craft_process", "materials"),
                with_fact="今天这一件靠{value}把它接住。",
                without_fact="复刻的做法尚未记录。",
            ),
            BeatBlueprint(
                beat_id="meet",
                title="相遇",
                intent="让新旧两件在同一画面里并置",
                emotion="舒展",
                fields=("occasion_tags", "product_name"),
                with_fact="它们在{value}重新遇上。",
                without_fact="它们还在等一次重新遇上的机会。",
            ),
        ),
    },
)

EN = StoryPhrases(
    premise="One {product}, and the hand skill behind {craft}, told to people who have "
    "never seen it made.",
    product_fallback="heritage object",
    anchor_claim="{value}",
    hedge="The maker tells us that ",
    artistic_note="narrative connective tissue, no factual basis",
    attributed_note="maker's account, not yet verified",
    templates={
        NarrativeTemplate.OBJECT_RECORD: (
            BeatBlueprint(
                beat_id="origin",
                title="Where it comes from",
                intent="place the object",
                emotion="still",
                fields=("region", "heritage_item", "craft_name"),
                with_fact="It comes from {value}.",
                without_fact="Its origin is not yet on record.",
            ),
            BeatBlueprint(
                beat_id="material",
                title="Material",
                intent="let the raw material be seen",
                emotion="attentive",
                fields=("materials", "dimensions"),
                with_fact="It is made of {value}.",
                without_fact="The material has not been logged.",
            ),
            BeatBlueprint(
                beat_id="process",
                title="Process",
                intent="show the step that costs the most work",
                emotion="taut",
                fields=("craft_process", "customization"),
                with_fact="The step that matters is {value}.",
                without_fact="The maker has yet to record the process.",
            ),
            BeatBlueprint(
                beat_id="today",
                title="Today",
                intent="return the object to present-day use",
                emotion="open",
                fields=("occasion_tags", "recipient_tags"),
                with_fact="Today it turns up at {value}.",
                without_fact="Where it belongs today is still being worked out.",
            ),
        ),
        NarrativeTemplate.ARTISAN_LIFE: (
            BeatBlueprint(
                beat_id="apprentice",
                title="Starting out",
                intent="connect the person to the craft",
                emotion="restrained",
                fields=("artisan_or_merchant_name", "craft_name"),
                with_fact="{value} has been this pair of hands' whole living.",
                without_fact="Nothing survives from the year the work began.",
            ),
            BeatBlueprint(
                beat_id="craft",
                title="Hand skill",
                intent="name the threshold in one gesture",
                emotion="attentive",
                fields=("craft_process", "materials"),
                with_fact="The whole skill sits in {value}.",
                without_fact="The knack has not been written down.",
            ),
            BeatBlueprint(
                beat_id="turn",
                title="The turn",
                intent="say why the craft nearly stopped",
                emotion="low",
                fields=("heritage_item", "region"),
                with_fact="{value} was, for a while, down to very few hands.",
                without_fact="The craft's decline lacks a checkable record.",
            ),
            BeatBlueprint(
                beat_id="pass_on",
                title="Passing it on",
                intent="land on the work still being done",
                emotion="level",
                fields=("customization", "symbolism"),
                with_fact="The work continues as {value}.",
                without_fact="The work continues, with no one writing it down.",
            ),
        ),
        NarrativeTemplate.TIME_DIALOGUE: (
            BeatBlueprint(
                beat_id="museum",
                title="In the collection",
                intent="open on an object that can be checked",
                emotion="grave",
                fields=("heritage_item", "cultural_background"),
                with_fact="The piece in the collection is {value}.",
                without_fact="No provenance has been found for the older piece.",
            ),
            BeatBlueprint(
                beat_id="pattern",
                title="The pattern",
                intent="read the symbol on the older piece",
                emotion="curious",
                fields=("symbolism", "meaning_tags"),
                with_fact="The pattern on it speaks of {value}.",
                without_fact="The pattern has no reliable reading yet.",
            ),
            BeatBlueprint(
                beat_id="remake",
                title="The remake",
                intent="show how the modern piece answers it",
                emotion="taut",
                fields=("craft_process", "materials"),
                with_fact="Today's piece catches it through {value}.",
                without_fact="The remake's method is not yet recorded.",
            ),
            BeatBlueprint(
                beat_id="meet",
                title="Meeting",
                intent="put old and new in one frame",
                emotion="open",
                fields=("occasion_tags", "product_name"),
                with_fact="The two meet again at {value}.",
                without_fact="They are still waiting to meet again.",
            ),
        ),
    },
)


#: Kept identical to :func:`heritagelink.growth_phrases.phrases_for` so a campaign
#: and its story never disagree about which language they are in.
_ZH_LANGUAGES = frozenset(
    {"chinese", "zh", "zh-cn", "简体中文", "中文", "bilingual", "中英双语"}
)


def story_phrases_for(language: str | None) -> StoryPhrases:
    """Pick the phrase table for a story language, defaulting to English."""
    return ZH if (language or "").strip().casefold() in _ZH_LANGUAGES else EN


__all__ = ["EN", "ZH", "BeatBlueprint", "StoryPhrases", "story_phrases_for"]
