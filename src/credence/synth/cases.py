"""Every synthetic case, fully specified. The gold labels are read from here."""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from credence.synth.dates import DateStyle, Language
from credence.synth.fields import CertificateFields


class Layout(StrEnum):
    CLASSIC = "classic"  # centred title, labelled lines, signature block
    TABLE = "table"  # two-column label/value grid
    LETTER = "letter"  # the fields embedded in prose
    CARD = "card"  # landscape, compact, with a logo
    INVOICE = "invoice"  # not a certificate
    MEMO = "memo"  # not a certificate


@dataclass(frozen=True)
class CaseSpec:
    id: str
    layout: Layout
    language: Language
    font: str
    date_style: DateStyle
    fields: CertificateFields
    hard: str
    """One sentence on what makes this case worth having, for the eval README."""
    expiry_date_style: DateStyle | None = None
    """A second date wording for the expiry, so one page mixes two formats."""
    standard: str | None = None
    accreditation: str | None = None
    holder_address: str | None = None
    signatory_title: str | None = None
    extra_pages: tuple[str, ...] = ()
    """Pages besides the certificate itself: "cover" before, "annex" after."""
    scanned: bool = False
    skew_degrees: float = 0.0
    seed: int = 0

    @property
    def page_count(self) -> int:
        return 1 + len(self.extra_pages)

    @property
    def is_certificate(self) -> bool:
        return self.layout not in (Layout.INVOICE, Layout.MEMO)


_EMPTY = CertificateFields()

CASES: tuple[CaseSpec, ...] = (
    CaseSpec(
        id="g01-classic-en-iso",
        layout=Layout.CLASSIC,
        language=Language.EN,
        font="Helvetica",
        date_style=DateStyle.ISO,
        fields=CertificateFields(
            issuer="Northgate Certification Services Ltd",
            holder="Harwell Precision Engineering plc",
            certificate_number="NCS-QMS-2024-0417",
            issue_date=date(2024, 3, 14),
            expiry_date=date(2027, 3, 13),
            scope="Design and manufacture of machined aluminium housings for medical devices",
            signatory="Margaret Okonkwo",
        ),
        standard="ISO 9001:2015",
        signatory_title="Head of Certification",
        hard="The baseline: clean layout, ISO dates, every field present.",
    ),
    CaseSpec(
        id="g02-classic-en-long",
        layout=Layout.CLASSIC,
        language=Language.EN,
        font="Times-Roman",
        date_style=DateStyle.LONG,
        fields=CertificateFields(
            issuer="Albion Quality Assurance Institute",
            holder="Fenwick & Dale Laboratories Limited",
            certificate_number="AQAI/17025/2023/0882",
            issue_date=date(2023, 11, 20),
            expiry_date=date(2026, 11, 19),
            scope="Calibration of pressure and temperature instruments",
            signatory="Dr Samuel Achterberg",
        ),
        standard="ISO/IEC 17025:2017",
        signatory_title="Technical Director",
        hard="Dates written out in words; the signatory carries an honorific and a title.",
    ),
    CaseSpec(
        id="g03-table-en-us-numeric",
        layout=Layout.TABLE,
        language=Language.EN,
        font="Helvetica",
        date_style=DateStyle.NUMERIC_MDY,
        fields=CertificateFields(
            issuer="Great Lakes Product Safety Inc.",
            holder="Marquette Industrial Controls LLC",
            certificate_number="GLPS-E-2024-11932",
            issue_date=date(2024, 7, 23),
            expiry_date=date(2029, 7, 22),
            scope="Industrial control panels, Type 4 enclosures, 600 V maximum",
            signatory="Dana R. Whitfield",
        ),
        standard="UL 508A",
        accreditation="Accredited by the National Accreditation Board, registration 0421",
        holder_address="1180 Industrial Parkway, Marquette, MI 49855, USA",
        signatory_title="Certification Manager",
        hard="US month-first numeric dates, plus an accreditation registration number "
        "and a street number as distractors for the certificate number.",
    ),
    CaseSpec(
        id="g04-table-en-mixed-dates",
        layout=Layout.TABLE,
        language=Language.EN,
        font="Times-Roman",
        date_style=DateStyle.NUMERIC_DMY,
        expiry_date_style=DateStyle.LONG,
        fields=CertificateFields(
            issuer="Caledonian Standards Bureau",
            holder="Strathmore Food Processing Ltd",
            certificate_number="CSB-FS-23-00561",
            issue_date=date(2023, 9, 18),
            expiry_date=date(2026, 9, 17),
            scope="Processing and packing of chilled ready meals",
            signatory="Fiona MacLeod",
        ),
        standard="BRCGS Food Safety Issue 9",
        signatory_title="Scheme Manager",
        hard="Two date formats on one page: day-first numeric for the issue date, "
        "words for the expiry.",
    ),
    CaseSpec(
        id="g05-letter-en-no-expiry",
        layout=Layout.LETTER,
        language=Language.EN,
        font="Times-Roman",
        date_style=DateStyle.LONG_US,
        fields=CertificateFields(
            issuer="Meridian Testing & Certification",
            holder="Oakridge Composites Corporation",
            certificate_number="MTC-2022-7730",
            issue_date=date(2022, 5, 26),
            expiry_date=None,
            scope="Type approval of glass-fibre reinforced pressure vessels, series OV-200",
            signatory="Priya Natarajan",
        ),
        standard="EN 13923:2006",
        signatory_title="Lead Assessor",
        hard="Prose layout with no expiry: the text says the certificate does not expire, "
        "so the gold is null and a guessed date is wrong.",
    ),
    CaseSpec(
        id="g06-letter-en-no-signatory",
        layout=Layout.LETTER,
        language=Language.EN,
        font="Helvetica",
        date_style=DateStyle.LONG,
        fields=CertificateFields(
            issuer="Westbrook Environmental Registrars",
            holder="Tern Valley Water Services",
            certificate_number="WER/14001/0093",
            issue_date=date(2024, 1, 29),
            expiry_date=date(2027, 1, 28),
            scope="Operation of wastewater treatment works at Tern Valley",
            signatory=None,
        ),
        standard="ISO 14001:2015",
        hard="Prose layout with no signature block at all; the signatory is null.",
    ),
    CaseSpec(
        id="g07-classic-es-long",
        layout=Layout.CLASSIC,
        language=Language.ES,
        font="Helvetica",
        date_style=DateStyle.LONG,
        fields=CertificateFields(
            issuer="Instituto Ibérico de Certificación S.A.",
            holder="Talleres Mecánicos Arganda S.L.",
            certificate_number="IIC-9001-2024-2210",
            issue_date=date(2024, 4, 16),
            expiry_date=date(2027, 4, 15),
            scope="Fabricación de componentes metálicos por mecanizado y soldadura",
            signatory="Carmen Villalobos Prieto",
        ),
        standard="ISO 9001:2015",
        signatory_title="Directora de Certificación",
        hard="Spanish labels and dates in words; accented names must survive intact.",
    ),
    CaseSpec(
        id="g08-table-fr-long",
        layout=Layout.TABLE,
        language=Language.FR,
        font="Times-Roman",
        date_style=DateStyle.LONG,
        fields=CertificateFields(
            issuer="Bureau Rhodanien de Certification",
            holder="Ateliers Chauvet et Fils SAS",
            certificate_number="BRC/45001/2023/118",
            issue_date=date(2023, 6, 21),
            expiry_date=date(2026, 6, 20),
            scope="Conception et fabrication de systèmes de levage industriels",
            signatory="Étienne Rousseau",
        ),
        standard="ISO 45001:2018",
        signatory_title="Responsable Certification",
        hard="French labels and dates; the signatory's name starts with an accented capital.",
    ),
    CaseSpec(
        id="g09-card-en-logo",
        layout=Layout.CARD,
        language=Language.EN,
        font="Courier",
        date_style=DateStyle.ISO,
        fields=CertificateFields(
            issuer="Southern Cross Compliance Pty Ltd",
            holder="Kestrel Avionics Pty Ltd",
            certificate_number="SCC-AS-2025-0071",
            issue_date=date(2025, 2, 17),
            expiry_date=date(2028, 2, 16),
            scope="Maintenance of avionics assemblies for fixed-wing aircraft",
            signatory="Hamish Teague",
        ),
        standard="AS9110C",
        signatory_title="Registrar",
        hard="Landscape card with a logo and a monospaced font; little text to go on.",
    ),
    CaseSpec(
        id="g10-classic-en-multipage",
        layout=Layout.CLASSIC,
        language=Language.EN,
        font="Helvetica",
        date_style=DateStyle.LONG,
        fields=CertificateFields(
            issuer="Northgate Certification Services Ltd",
            holder="Hollins Medical Devices Ltd",
            certificate_number="NCS-MD-2024-0902",
            issue_date=date(2024, 10, 15),
            expiry_date=date(2027, 10, 14),
            scope="Design and manufacture of sterile single-use syringes",
            signatory="Margaret Okonkwo",
        ),
        standard="ISO 13485:2016",
        signatory_title="Head of Certification",
        extra_pages=("cover", "annex"),
        hard="Three pages: a cover letter with its own date and reference, the certificate, "
        "and an annex of sites. The fields are on page two only.",
    ),
    CaseSpec(
        id="g11-scan-classic-en",
        layout=Layout.CLASSIC,
        language=Language.EN,
        font="Times-Roman",
        date_style=DateStyle.LONG,
        fields=CertificateFields(
            issuer="Pennine Assessment Services",
            holder="Brackenfield Plastics Ltd",
            certificate_number="PAS-Q-2023-3348",
            issue_date=date(2023, 8, 24),
            expiry_date=date(2026, 8, 23),
            scope="Injection moulding of thermoplastic components",
            signatory="Rebecca Thwaite",
        ),
        standard="ISO 9001:2015",
        signatory_title="Certification Director",
        scanned=True,
        skew_degrees=0.8,
        seed=11,
        hard="Image-only, slightly skewed. No text layer; the model reads pixels.",
    ),
    CaseSpec(
        id="g12-scan-table-es",
        layout=Layout.TABLE,
        language=Language.ES,
        font="Helvetica",
        date_style=DateStyle.NUMERIC_DMY,
        fields=CertificateFields(
            issuer="Certificadora del Levante S.L.",
            holder="Conservas Mar Menor S.A.",
            certificate_number="CL-22000-2024-0366",
            issue_date=date(2024, 5, 30),
            expiry_date=date(2027, 5, 29),
            scope="Elaboración y envasado de conservas de pescado",
            signatory="Jorge Martínez Soler",
        ),
        standard="ISO 22000:2018",
        signatory_title="Director Técnico",
        scanned=True,
        skew_degrees=-1.2,
        seed=12,
        hard="Scanned Spanish table, skewed the other way, day-first numeric dates.",
    ),
    CaseSpec(
        id="g13-scan-letter-fr-no-signatory",
        layout=Layout.LETTER,
        language=Language.FR,
        font="Times-Roman",
        date_style=DateStyle.NUMERIC_DMY,
        fields=CertificateFields(
            issuer="Office Atlantique de Conformité",
            holder="Chantiers Navals de Saint-Brieuc",
            certificate_number="OAC-2024-0510-M",
            issue_date=date(2024, 9, 19),
            expiry_date=date(2027, 9, 18),
            scope="Construction et réparation de coques en acier",
            signatory=None,
        ),
        standard="ISO 9001:2015",
        extra_pages=("annex",),
        scanned=True,
        skew_degrees=0.5,
        seed=13,
        hard="Two scanned pages of French prose with no signature; "
        "the annex adds more names and numbers to ignore.",
    ),
    CaseSpec(
        id="g14-scan-card-en",
        layout=Layout.CARD,
        language=Language.EN,
        font="Helvetica",
        date_style=DateStyle.NUMERIC_MDY,
        fields=CertificateFields(
            issuer="Cascadia Safety Certification Corp.",
            holder="Willamette Lift Systems Inc.",
            certificate_number="CSC-2025-1187",
            issue_date=date(2025, 1, 21),
            expiry_date=date(2026, 1, 20),
            scope="Annual inspection of passenger elevators, units 1 to 6, Pioneer Tower",
            signatory="Luis Ortega",
        ),
        standard="ASME A17.1",
        signatory_title="Chief Inspector",
        scanned=True,
        skew_degrees=1.4,
        seed=14,
        hard="Scanned landscape card with a logo and a one-year validity.",
    ),
    CaseSpec(
        id="g15-classic-en-dotted",
        layout=Layout.CLASSIC,
        language=Language.EN,
        font="Helvetica",
        date_style=DateStyle.DOTTED,
        fields=CertificateFields(
            issuer="Baltic Conformity Assessment OÜ",
            holder="Nordhavn Marine Electronics A/S",
            certificate_number="BCA-EMC-2024-0458",
            issue_date=date(2024, 11, 27),
            expiry_date=date(2029, 11, 26),
            scope="Electromagnetic compatibility of shipboard navigation displays, model ND-7",
            signatory="Kristjan Põder",
        ),
        standard="IEC 60945:2002",
        accreditation="Accredited by the Estonian Accreditation Centre, certificate L123",
        signatory_title="Lead Engineer",
        hard="Dotted European dates and an accreditation line that itself mentions a "
        "certificate number which is not this certificate's.",
    ),
    CaseSpec(
        id="g16-table-en-no-expiry-no-signatory",
        layout=Layout.TABLE,
        language=Language.EN,
        font="Courier",
        date_style=DateStyle.ISO,
        fields=CertificateFields(
            issuer="Ridgeway Materials Testing Ltd",
            holder="Coombe Quarries Ltd",
            certificate_number="RMT-CA-2023-0204",
            issue_date=date(2023, 3, 2),
            expiry_date=None,
            scope="Conformity of crushed limestone aggregate, grade 20/40, batch 23-0881",
            signatory=None,
        ),
        standard="EN 12620:2002+A1:2008",
        hard="Both expiry and signatory absent on an otherwise complete grid; "
        "two nulls are correct, and a batch number is a distractor.",
    ),
    CaseSpec(
        id="n01-invoice-en",
        layout=Layout.INVOICE,
        language=Language.EN,
        font="Helvetica",
        date_style=DateStyle.ISO,
        fields=_EMPTY,
        hard="Not a certificate. An invoice with a number, dates and two company names; "
        "every field should be null.",
    ),
    CaseSpec(
        id="n02-scan-memo-es",
        layout=Layout.MEMO,
        language=Language.ES,
        font="Times-Roman",
        date_style=DateStyle.LONG,
        fields=_EMPTY,
        scanned=True,
        skew_degrees=-0.6,
        seed=22,
        hard="Not a certificate. A scanned Spanish internal memo that mentions an audit "
        "and a certificate by number; every field should still be null.",
    ),
)

assert len({c.id for c in CASES}) == len(CASES), "case ids must be unique"
