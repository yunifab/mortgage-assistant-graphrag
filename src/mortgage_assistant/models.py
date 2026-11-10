"""Data shapes shared by the pipeline: a Section of the policy and a Chunk of text."""

from dataclasses import asdict, dataclass, field


@dataclass
class Section:
    """One numbered part of the policy, e.g. 'AB-5.5.12 Woonboot met vaste ligplaats'.

    id:      unique key, part code + number (the same number exists in several parts)
    part:    'Versiebeheer', 'Acceptatiebeleid', 'Beheerbeleid' or 'Bijlagen'
    chapter: chapter heading, e.g. 'Hoofdstuk 5 | Onderpand en waardebepaling'
    number:  section number as printed, e.g. '5.5.12' (empty for intro sections)
    level:   1 = chapter, 2 = x.y, 3 = x.y.z, 4 = x.y.z.w
    pages:   physical PDF pages (1-based) the section text appears on
    explain_icon: True if the section shows the 🔍 icon ('an exception is possible, see Explain')
    """

    id: str
    part: str
    chapter: str
    number: str
    title: str
    level: int
    parent_id: str | None
    pages: list[int] = field(default_factory=list)
    text: str = ""
    explain_icon: bool = False
    explain_icon_lines: list[str] = field(default_factory=list)  # the text next to each icon

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Definition:
    """One entry of Bijlage 2 (Definitielijst): a policy term and what it means."""

    term: str
    text: str
    page: int

    @property
    def id(self) -> str:
        return "DEF-" + "".join(ch if ch.isalnum() else "-" for ch in self.term.lower()).strip("-")

    def to_dict(self) -> dict:
        return asdict(self) | {"id": self.id}


@dataclass
class Chunk:
    """A piece of a section small enough to embed and give to the LLM."""

    id: str
    section_id: str
    part: str
    chapter: str
    section_number: str
    section_title: str
    pages: list[int]
    text: str

    @property
    def heading_path(self) -> str:
        """Where the chunk sits in the document, e.g. 'Acceptatiebeleid > Hoofdstuk 5 ... > 5.5.12 Woonboot'."""
        section = f"{self.section_number} {self.section_title}".strip()
        parts = [self.part, self.chapter, section]
        # Drop empty and repeated items (a chapter-level section repeats the chapter title)
        out: list[str] = []
        for p in parts:
            if p and p not in out and not (out and p in out[-1]):
                out.append(p)
        return " > ".join(out)

    @property
    def text_for_embedding(self) -> str:
        """The heading path is added so a chunk like 'Maximaal 80%...' still says what it is about."""
        return f"{self.heading_path}\n{self.text}"

    def to_dict(self) -> dict:
        return asdict(self)
