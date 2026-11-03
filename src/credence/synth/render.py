"""Render a case specification to a text-based PDF with reportlab.

Every layout prints the gold values verbatim, so a text extraction of the
page contains them. Distractors (letter dates, reference numbers, names of
other people) are printed too, on purpose.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from io import BytesIO

from reportlab.lib.pagesizes import A4, A5, LETTER, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen.canvas import Canvas

from credence.synth.cases import CaseSpec, Layout
from credence.synth.dates import DateStyle, Language, format_date

_BOLD = {"Helvetica": "Helvetica-Bold", "Times-Roman": "Times-Bold", "Courier": "Courier-Bold"}


@dataclass(frozen=True)
class Words:
    title: str
    certify: str
    meets: str
    issuer: str
    holder: str
    address: str
    number: str
    issue: str
    expiry: str
    scope: str
    standard: str
    signed: str
    on_behalf: str
    no_expiry: str
    unsigned: str
    letter_date: str
    page: str


WORDS: dict[Language, Words] = {
    Language.EN: Words(
        title="Certificate of Registration",
        certify="This is to certify that",
        meets="has been assessed and found to meet the requirements of",
        issuer="Issued by",
        holder="Certificate holder",
        address="Address",
        number="Certificate No.",
        issue="Date of issue",
        expiry="Valid until",
        scope="Scope",
        standard="Standard",
        signed="Signed",
        on_behalf="for and on behalf of",
        no_expiry="This certificate does not expire.",
        unsigned="Issued electronically and valid without signature.",
        letter_date="Date",
        page="Page {n} of {total}",
    ),
    Language.ES: Words(
        title="Certificado de Registro",
        certify="Se certifica que",
        meets="ha sido evaluada y cumple los requisitos de la norma",
        issuer="Emitido por",
        holder="Titular del certificado",
        address="Dirección",
        number="Certificado N.º",
        issue="Fecha de emisión",
        expiry="Válido hasta",
        scope="Alcance",
        standard="Norma",
        signed="Firmado",
        on_behalf="en nombre de",
        no_expiry="Este certificado no caduca.",
        unsigned="Emitido electrónicamente y válido sin firma.",
        letter_date="Fecha",
        page="Página {n} de {total}",
    ),
    Language.FR: Words(
        title="Certificat d'Enregistrement",
        certify="Nous certifions que",
        meets="a été évaluée et satisfait aux exigences de la norme",
        issuer="Délivré par",
        holder="Titulaire du certificat",
        address="Adresse",
        number="Certificat n°",
        issue="Date d'émission",
        expiry="Valable jusqu'au",
        scope="Portée",
        standard="Norme",
        signed="Signé",
        on_behalf="pour le compte de",
        no_expiry="Ce certificat n'a pas de date d'expiration.",
        unsigned="Délivré par voie électronique et valable sans signature.",
        letter_date="Date",
        page="Page {n} sur {total}",
    ),
}


class _Page:
    """A canvas with a cursor that moves down the page."""

    def __init__(self, c: Canvas, spec: CaseSpec, width: float, height: float) -> None:
        self.c = c
        self.spec = spec
        self.width = width
        self.height = height
        self.margin = 22 * mm
        self.y = height - self.margin
        self.font = spec.font
        self.bold = _BOLD[spec.font]

    @property
    def text_width(self) -> float:
        return self.width - 2 * self.margin

    def gap(self, pts: float) -> None:
        self.y -= pts

    def line(
        self, text: str, size: float = 11, *, bold: bool = False, x: float | None = None
    ) -> None:
        self.c.setFont(self.bold if bold else self.font, size)
        self.c.drawString(self.margin if x is None else x, self.y, text)
        self.y -= size * 1.45

    def centred(self, text: str, size: float = 11, *, bold: bool = False) -> None:
        self.c.setFont(self.bold if bold else self.font, size)
        self.c.drawCentredString(self.width / 2, self.y, text)
        self.y -= size * 1.45

    def paragraph(
        self, text: str, size: float = 11, *, centred: bool = False, width: float | None = None
    ) -> None:
        font = self.font
        for part in simpleSplit(text, font, size, width or self.text_width):
            if centred:
                self.centred(part, size)
            else:
                self.line(part, size)

    def labelled(self, label: str, value: str, size: float = 11, *, col: float = 48 * mm) -> None:
        """One grid row: bold label in the left column, wrapped value in the right."""
        self.c.setFont(self.bold, size)
        self.c.drawString(self.margin, self.y, label)
        self.c.setFont(self.font, size)
        for part in simpleSplit(value, self.font, size, self.text_width - col):
            self.c.drawString(self.margin + col, self.y, part)
            self.y -= size * 1.45
        self.y -= size * 0.4

    def rule(self) -> None:
        self.c.setLineWidth(0.6)
        self.c.line(self.margin, self.y, self.width - self.margin, self.y)
        self.y -= 16

    def footer(self, n: int, total: int) -> None:
        self.c.setFont(self.font, 8)
        words = WORDS[self.spec.language]
        self.c.drawRightString(
            self.width - self.margin, 12 * mm, words.page.format(n=n, total=total)
        )


def _issue(spec: CaseSpec) -> str:
    assert spec.fields.issue_date is not None
    return format_date(spec.fields.issue_date, spec.date_style, spec.language)


def _expiry(spec: CaseSpec) -> str | None:
    if spec.fields.expiry_date is None:
        return None
    style = spec.expiry_date_style or spec.date_style
    return format_date(spec.fields.expiry_date, style, spec.language)


def _initials(name: str) -> str:
    return "".join(w[0] for w in name.split() if w[0].isupper())[:3]


def _logo(p: _Page, x: float, y: float, r: float, name: str) -> None:
    c = p.c
    c.setLineWidth(1.4)
    c.circle(x, y, r, stroke=1, fill=0)
    c.circle(x, y, r * 0.72, stroke=1, fill=0)
    c.setFont(p.bold, r * 0.55)
    c.drawCentredString(x, y - r * 0.2, _initials(name))


def _signature(p: _Page, *, right: bool = False) -> None:
    spec, words = p.spec, WORDS[p.spec.language]
    f = spec.fields
    x = p.width - p.margin - 70 * mm if right else p.margin
    if f.signatory is None:
        p.line(words.unsigned, 9, x=x)
        return
    p.gap(14)
    p.c.setLineWidth(0.6)
    p.c.line(x, p.y, x + 70 * mm, p.y)
    p.gap(12)
    p.line(f.signatory, 11, bold=True, x=x)
    if spec.signatory_title:
        p.line(spec.signatory_title, 9, x=x)
    assert f.issuer is not None
    for part in simpleSplit(f"{words.on_behalf} {f.issuer}", p.font, 9, 70 * mm):
        p.line(part, 9, x=x)


def _classic(p: _Page) -> None:
    spec, words, f = p.spec, WORDS[p.spec.language], p.spec.fields
    assert f.issuer and f.holder and f.certificate_number and f.scope
    p.centred(f.issuer, 14, bold=True)
    if spec.accreditation:
        p.centred(spec.accreditation, 8)
    p.gap(26)
    p.centred(words.title, 24, bold=True)
    p.gap(22)
    p.centred(words.certify, 11)
    p.gap(4)
    p.centred(f.holder, 16, bold=True)
    if spec.holder_address:
        p.centred(spec.holder_address, 10)
    p.gap(10)
    p.centred(words.meets, 11)
    p.centred(spec.standard or "", 13, bold=True)
    p.gap(14)
    p.centred(words.scope, 10, bold=True)
    p.paragraph(f.scope, 11, centred=True, width=p.text_width - 30 * mm)
    p.gap(22)
    p.centred(f"{words.number} {f.certificate_number}", 12, bold=True)
    p.gap(6)
    p.centred(f"{words.issue}: {_issue(spec)}", 11)
    expiry = _expiry(spec)
    p.centred(f"{words.expiry}: {expiry}" if expiry else words.no_expiry, 11)
    p.gap(30)
    _signature(p, right=True)


def _table(p: _Page) -> None:
    spec, words, f = p.spec, WORDS[p.spec.language], p.spec.fields
    assert f.issuer and f.holder and f.certificate_number and f.scope
    p.line(f.issuer, 13, bold=True)
    if spec.accreditation:
        p.c.setFont(p.font, 8)
        p.c.drawRightString(p.width - p.margin, p.y + 13 * 1.45, spec.accreditation)
    p.rule()
    p.gap(16)
    p.line(words.title, 20, bold=True)
    p.gap(18)
    p.labelled(words.number, f.certificate_number, 12)
    p.labelled(words.holder, f.holder)
    if spec.holder_address:
        p.labelled(words.address, spec.holder_address)
    p.labelled(words.standard, spec.standard or "")
    p.labelled(words.scope, f.scope)
    p.labelled(words.issue, _issue(spec))
    expiry = _expiry(spec)
    p.labelled(words.expiry, expiry or words.no_expiry)
    p.gap(16)
    p.rule()
    if f.signatory:
        title = f", {spec.signatory_title}" if spec.signatory_title else ""
        p.labelled(words.signed, f"{f.signatory}{title}")
    else:
        p.line(words.unsigned, 9)


_PROSE: dict[Language, dict[str, str]] = {
    Language.EN: {
        "body": (
            "{issuer} confirms that {holder}{address} has been assessed against {standard} "
            "and found to comply for the following scope: {scope}."
        ),
        "dates": "Certificate {number} was issued on {issue} and is valid until {expiry}.",
        "no_expiry": "Certificate {number} was issued on {issue}. {no_expiry}",
        "closing": "Signed on behalf of {issuer},",
    },
    Language.ES: {
        "body": (
            "{issuer} confirma que {holder}{address} ha sido evaluada conforme a la norma "
            "{standard} y cumple sus requisitos para el siguiente alcance: {scope}."
        ),
        "dates": "El certificado {number} fue emitido el {issue} y es válido hasta el {expiry}.",
        "no_expiry": "El certificado {number} fue emitido el {issue}. {no_expiry}",
        "closing": "Firmado en nombre de {issuer},",
    },
    Language.FR: {
        "body": (
            "{issuer} confirme que {holder}{address} a été évaluée selon la norme {standard} "
            "et satisfait à ses exigences pour la portée suivante : {scope}."
        ),
        "dates": (
            "Le certificat {number} a été délivré le {issue} et est valable jusqu'au {expiry}."
        ),
        "no_expiry": "Le certificat {number} a été délivré le {issue}. {no_expiry}",
        "closing": "Signé pour le compte de {issuer},",
    },
}


def _letter(p: _Page) -> None:
    spec, words, f = p.spec, WORDS[p.spec.language], p.spec.fields
    assert f.issuer and f.holder and f.certificate_number and f.scope and f.issue_date
    prose = _PROSE[spec.language]
    p.line(f.issuer, 13, bold=True)
    p.line("Certification Body / Organismo de certificación / Organisme certificateur", 8)
    p.rule()
    # The letter is dated a few days after the issue date: a distractor on purpose.
    letter_date = format_date(f.issue_date + timedelta(days=3), spec.date_style, spec.language)
    p.c.setFont(p.font, 10)
    p.c.drawRightString(p.width - p.margin, p.y, f"{words.letter_date}: {letter_date}")
    p.gap(28)
    p.line(words.title, 18, bold=True)
    p.gap(16)
    address = f", {spec.holder_address}," if spec.holder_address else ""
    p.paragraph(
        prose["body"].format(
            issuer=f.issuer, holder=f.holder, address=address, standard=spec.standard,
            scope=f.scope,
        ),
        11.5,
    )  # fmt: skip
    p.gap(10)
    expiry = _expiry(spec)
    key = "dates" if expiry else "no_expiry"
    p.paragraph(
        prose[key].format(
            number=f.certificate_number, issue=_issue(spec), expiry=expiry,
            no_expiry=words.no_expiry,
        ),
        11.5,
    )  # fmt: skip
    p.gap(24)
    if f.signatory:
        p.line(prose["closing"].format(issuer=f.issuer), 11)
    _signature(p)


def _card(p: _Page) -> None:
    spec, words, f = p.spec, WORDS[p.spec.language], p.spec.fields
    assert f.issuer and f.holder and f.certificate_number and f.scope
    p.margin = 14 * mm
    p.y = p.height - p.margin - 6 * mm
    _logo(p, p.margin + 9 * mm, p.y - 2 * mm, 9 * mm, f.issuer)
    p.line(f.issuer, 12, bold=True, x=p.margin + 22 * mm)
    p.line(words.title, 15, bold=True, x=p.margin + 22 * mm)
    p.gap(14)
    col = 46 * mm
    p.labelled(words.holder, f.holder, 10, col=col)
    p.labelled(words.standard, spec.standard or "", 10, col=col)
    p.labelled(words.scope, f.scope, 10, col=col)
    p.labelled(words.number, f.certificate_number, 10, col=col)
    p.labelled(words.issue, _issue(spec), 10, col=col)
    expiry = _expiry(spec)
    p.labelled(words.expiry, expiry or words.no_expiry, 10, col=col)
    p.y = p.margin + 16 * mm
    _signature(p, right=True)


_COVER: dict[Language, dict[str, str]] = {
    Language.EN: {
        "ref": "Our reference",
        "salutation": "Dear Certification Contact,",
        "body": (
            "Please find enclosed certificate {number} issued to {holder}, together with "
            "its annex listing the sites covered. The certificate remains the property of "
            "{issuer} and must be returned on request. Surveillance audits are planned at "
            "twelve-month intervals; our client services team will contact you to agree dates."
        ),
        "closing": "Yours faithfully,",
        "sender": "Thomas Greyling",
        "sender_title": "Client Services Coordinator",
        "enc": "Enc. Certificate and annex ({total} pages in total)",
    },
    Language.ES: {
        "ref": "Nuestra referencia",
        "salutation": "Estimados señores:",
        "body": (
            "Adjuntamos el certificado {number} emitido a {holder}, junto con su anexo. "
            "El certificado sigue siendo propiedad de {issuer} y deberá devolverse a petición."
        ),
        "closing": "Atentamente,",
        "sender": "Lucía Fernández Ruiz",
        "sender_title": "Coordinadora de Clientes",
        "enc": "Adj. Certificado y anexo ({total} páginas en total)",
    },
    Language.FR: {
        "ref": "Notre référence",
        "salutation": "Madame, Monsieur,",
        "body": (
            "Veuillez trouver ci-joint le certificat {number} délivré à {holder}, accompagné "
            "de son annexe. Le certificat reste la propriété de {issuer} et doit être restitué "
            "sur demande."
        ),
        "closing": "Veuillez agréer nos salutations distinguées,",
        "sender": "Camille Berthier",
        "sender_title": "Coordinatrice Clientèle",
        "enc": "P.J. Certificat et annexe ({total} pages au total)",
    },
}


def _cover(p: _Page, total: int) -> None:
    spec, words, f = p.spec, WORDS[p.spec.language], p.spec.fields
    assert f.issuer and f.holder and f.certificate_number and f.issue_date
    t = _COVER[spec.language]
    p.line(f.issuer, 13, bold=True)
    p.rule()
    letter_date = format_date(f.issue_date + timedelta(days=3), spec.date_style, spec.language)
    p.line(f"{words.letter_date}: {letter_date}", 10)
    p.line(f"{t['ref']}: {spec.id.upper()}/COV/{f.issue_date.year}", 10)
    p.gap(16)
    p.line(f.holder, 11, bold=True)
    if spec.holder_address:
        p.line(spec.holder_address, 10)
    p.gap(16)
    p.line(t["salutation"], 11)
    p.gap(6)
    p.paragraph(t["body"].format(number=f.certificate_number, holder=f.holder, issuer=f.issuer), 11)
    p.gap(16)
    p.line(t["closing"], 11)
    p.gap(22)
    p.line(t["sender"], 11, bold=True)
    p.line(t["sender_title"], 9)
    p.gap(20)
    p.line(t["enc"].format(total=total), 9)


_ANNEX: dict[Language, dict[str, str]] = {
    Language.EN: {
        "title": "Annex to certificate {number}",
        "intro": "Sites covered by the scope of the certificate:",
        "sites": "Head office and plant 1|Plant 2 (assembly)|Distribution centre",
        "auditor": "Lead auditor: {name}",
        "auditor_name": "Marcus Lindqvist",
    },
    Language.ES: {
        "title": "Anexo al certificado {number}",
        "intro": "Centros cubiertos por el alcance del certificado:",
        "sites": "Sede central y planta 1|Planta 2 (montaje)|Centro de distribución",
        "auditor": "Auditor jefe: {name}",
        "auditor_name": "Andrés Caballero",
    },
    Language.FR: {
        "title": "Annexe au certificat {number}",
        "intro": "Sites couverts par la portée du certificat :",
        "sites": "Siège et atelier 1|Atelier 2 (assemblage)|Centre de distribution",
        "auditor": "Auditeur principal : {name}",
        "auditor_name": "Marc Lefèvre",
    },
}

_STREETS = ("14 Mill Lane", "Unit 7, Riverside Park", "Avenida del Puerto 221", "Quai des Ormes 3")


def _annex(p: _Page) -> None:
    spec, words, f = p.spec, WORDS[p.spec.language], p.spec.fields
    assert f.issuer and f.holder and f.certificate_number
    t = _ANNEX[spec.language]
    p.line(f.issuer, 13, bold=True)
    p.rule()
    p.gap(10)
    p.line(t["title"].format(number=f.certificate_number), 16, bold=True)
    p.line(f.holder, 11)
    p.gap(14)
    p.line(t["intro"], 11)
    p.gap(6)
    for i, site in enumerate(t["sites"].split("|")):
        p.line(f"{i + 1}. {site}", 11, bold=True)
        p.line(f"   {_STREETS[(spec.seed + i) % len(_STREETS)]}", 10)
        p.gap(4)
    p.gap(16)
    p.line(t["auditor"].format(name=t["auditor_name"]), 10)
    p.line(f"{words.number} {f.certificate_number}", 10)


def _invoice(p: _Page) -> None:
    p.line("Northgate Certification Services Ltd", 13, bold=True)
    p.line("Unit 4, Priory Business Park, Abingdon OX14 3YS, United Kingdom", 9)
    p.rule()
    p.gap(14)
    p.line("INVOICE", 22, bold=True)
    p.gap(10)
    p.labelled("Invoice No.", "INV-2024-5523")
    p.labelled("Invoice date", "2024-06-03")
    p.labelled("Due date", "2024-07-03")
    p.labelled("Bill to", "Harwell Precision Engineering plc")
    p.labelled("Your reference", "PO 44819")
    p.gap(14)
    p.rule()
    p.labelled("Description", "ISO 9001:2015 stage 2 certification audit, 2 auditor days")
    p.labelled("Amount", "GBP 2,400.00")
    p.labelled("VAT 20%", "GBP 480.00")
    p.labelled("Total due", "GBP 2,880.00")
    p.rule()
    p.gap(14)
    p.paragraph(
        "Payment within 30 days to the account stated on our terms of business. "
        "Please quote the invoice number. The certificate will be released on receipt of "
        "payment.",
        10,
    )


def _memo(p: _Page) -> None:
    p.line("MEMORANDO INTERNO", 18, bold=True)
    p.rule()
    p.gap(8)
    p.labelled("De", "Dirección de Calidad", col=30 * mm)
    p.labelled("Para", "Jefes de planta", col=30 * mm)
    p.labelled("Fecha", "8 de abril de 2025", col=30 * mm)
    p.labelled("Asunto", "Preparación de la auditoría de renovación", col=30 * mm)
    p.rule()
    p.gap(10)
    p.paragraph(
        "Nuestro certificado IIC-9001-2021-0877 caduca el 30 de junio de 2025. El organismo "
        "certificador ha propuesto realizar la auditoría de renovación los días 19 y 20 de mayo. "
        "Cada jefe de planta debe revisar los registros de formación, calibración y acciones "
        "correctivas antes del 5 de mayo y comunicar cualquier incidencia a esta dirección.",
        11,
    )
    p.gap(10)
    p.paragraph(
        "Recordad que el alcance no ha cambiado desde la última renovación y que el auditor "
        "jefe será el mismo que en 2022.",
        11,
    )
    p.gap(20)
    p.line("Dirección de Calidad", 11, bold=True)


def _page_size(spec: CaseSpec) -> tuple[float, float]:
    if spec.layout is Layout.CARD:
        return landscape(A5)
    if spec.date_style is DateStyle.NUMERIC_MDY or spec.date_style is DateStyle.LONG_US:
        return LETTER
    return A4


def render(spec: CaseSpec) -> bytes:
    """The case as a text-based PDF. Deterministic: same spec, same bytes."""
    width, height = _page_size(spec)
    buf = BytesIO()
    c = Canvas(buf, pagesize=(width, height), invariant=1, pageCompression=0)
    c.setTitle(WORDS[spec.language].title if spec.is_certificate else spec.layout.value)
    c.setCreator("credence.synth")
    total = spec.page_count
    n = 0

    def page(draw: Callable[[_Page], None]) -> None:
        nonlocal n
        n += 1
        p = _Page(c, spec, width, height)
        draw(p)
        if total > 1:
            p.footer(n, total)
        c.showPage()

    if "cover" in spec.extra_pages:
        page(lambda p: _cover(p, total))
    main = {
        Layout.CLASSIC: _classic,
        Layout.TABLE: _table,
        Layout.LETTER: _letter,
        Layout.CARD: _card,
        Layout.INVOICE: _invoice,
        Layout.MEMO: _memo,
    }[spec.layout]
    page(main)
    if "annex" in spec.extra_pages:
        page(_annex)
    c.save()
    return buf.getvalue()
