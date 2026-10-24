"""Wording for synthetic claims: date and amount formats, labels and loss descriptions."""

import random
from datetime import date

from triage.schemas import Category

INSURERS = ("Harbour Lane Insurance", "Northbridge Mutual", "Kestrel General")
CARS = (
    "Ford Focus",
    "Vauxhall Corsa",
    "Volkswagen Golf",
    "Toyota Yaris",
    "Nissan Qashqai",
    "Kia Sportage",
    "BMW 1 Series",
    "Skoda Octavia",
)

NORMAL_DATE_STYLES = ("dmy_slash", "long", "iso", "month_first")


def ordinal(day: int) -> str:
    suffix = "th" if 11 <= day % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


# English names written out so output does not depend on the machine locale.
MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def format_date(d: date, style: str) -> str:
    month = MONTHS[d.month - 1]
    if style == "dmy_slash":
        return f"{d.day:02d}/{d.month:02d}/{d.year}"
    if style == "long":
        return f"{d.day} {month} {d.year}"
    if style == "iso":
        return d.isoformat()
    if style == "month_first":
        return f"{month} {d.day}, {d.year}"
    if style == "ordinal_words":
        return f"the {ordinal(d.day)} day of {month} in the year {d.year}"
    if style == "short_weekday":
        return f"{WEEKDAYS[d.weekday()]} {ordinal(d.day)} {month[:3]} '{d.year % 100:02d}"
    raise ValueError(f"unknown date style {style}")


def format_amount(amount: float, rng: random.Random) -> str:
    whole = amount == int(amount)
    styles = ["£{:,.2f}", "GBP {:.2f}", "{:,.2f} pounds"]
    if whole:
        styles.append("£{:,.0f}")
    return rng.choice(styles).format(amount)


LABELS = {
    "claim_number": ("Claim number", "Claim reference", "Our ref."),
    "policy_number": ("Policy number", "Policy no.", "Policy reference"),
    "date_of_loss": ("Date of loss", "Date of incident", "Incident date"),
    "claimant_role": ("Claimant type", "Claiming as", "You are the"),
    "amount_claimed": ("Amount claimed", "Estimated cost", "Total claimed"),
    "location": ("Location of loss", "Where it happened", "Incident location"),
    "policy_start_date": ("Policy start date", "Cover start", "Insured since"),
    "police_report_number": ("Police reference", "Crime reference number", "Police report no."),
    "name": ("Claimant name", "Full name", "Name"),
    "address": ("Address", "Correspondence address", "Home address"),
    "phone": ("Telephone", "Phone", "Contact number"),
    "email": ("Email", "Email address", "E-mail"),
    "ni_number": ("National Insurance no.", "NI number", "NINO"),
    "vehicle_registration": ("Vehicle registration", "Reg. number", "Vehicle reg"),
}

ROLE_WORDS = {
    "policyholder": ("Policyholder", "Policy holder", "The insured"),
    "third_party": ("Third party", "Third-party claimant", "Not the policyholder (third party)"),
    "representative": ("Representative of the policyholder", "Broker acting for the insured"),
}

# Loss descriptions: (incident, damage, action) parts per category.
STORIES: dict[Category, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = {
    Category.MOTOR_COLLISION: (
        (
            "While I was queueing at a roundabout, another car drove into the back of my {car}.",
            "I was reversing out of a parking space when a van pulled out and hit the side of my {car}.",
            "A driver ran a red light at a junction and struck the front of my {car}.",
            "In heavy rain my {car} skidded on a bend and hit a stone wall.",
        ),
        (
            "The rear bumper, boot lid and one light cluster are damaged.",
            "Both nearside doors are dented and the wing mirror is broken.",
            "The bonnet, front bumper and radiator need replacing.",
            "The front wheel and suspension arm are bent and the car cannot be driven.",
        ),
        (
            "Details were exchanged with the other driver at the scene.",
            "The car was recovered to a local garage, which has quoted for the repair.",
            "Photos of the damage were taken at the scene and are available.",
        ),
    ),
    Category.MOTOR_THEFT: (
        (
            "My {car} was stolen overnight from the street outside my home.",
            "I parked my {car} at the station car park in the morning and it was gone in the evening.",
            "Thieves broke into my house, took the keys and drove away in my {car}.",
        ),
        (
            "The car has not been recovered.",
            "The car has not been found and the tracking service shows no signal.",
            "Personal belongings, including a child seat, were inside the car.",
        ),
        (
            "I reported the theft to the police the same day.",
            "I still have both sets of keys apart from the stolen one.",
            "CCTV from a neighbour may show the vehicle being taken.",
        ),
    ),
    Category.PROPERTY_WATER: (
        (
            "A pipe under the bathroom floor burst and water came through the kitchen ceiling.",
            "The washing machine hose split while we were out and flooded the utility room.",
            "Heavy rain overflowed a blocked gutter and water ran down the inside of the back wall.",
            "The water tank in the loft leaked and soaked the bedroom ceiling below.",
        ),
        (
            "The ceiling plaster has collapsed in one corner and the flooring is ruined.",
            "Skirting boards, a carpet and the lower kitchen units are water damaged.",
            "The wall needs drying out and replastering, and a sofa was soaked.",
        ),
        (
            "A plumber stopped the leak the same day and has invoiced for the call out.",
            "A drying company has been booked and has provided an estimate.",
            "I turned off the water at the stopcock and moved what I could.",
        ),
    ),
    Category.PROPERTY_FIRE: (
        (
            "A pan of oil caught fire on the hob and the flames spread to the extractor hood.",
            "An electrical fault in the garage consumer unit started a fire.",
            "A candle left on a windowsill set fire to the curtains in the living room.",
        ),
        (
            "The kitchen units and ceiling are smoke damaged and need replacing.",
            "The garage roof and the contents stored inside were destroyed.",
            "Soot damage affects the whole ground floor and the window frame is burnt.",
        ),
        (
            "The fire service attended and put the fire out.",
            "Nobody was hurt and the fire was put out with an extinguisher.",
            "We are staying with family until the smell of smoke is cleared.",
        ),
    ),
    Category.LIABILITY: (
        (
            "A customer slipped on a wet floor in the shop owned by your policyholder.",
            "Your policyholder's dog ran out of their garden and bit me on the leg.",
            "A roof tile fell from your policyholder's house and struck my parked car.",
            "Water from your policyholder's flat leaked into my flat below and damaged my belongings.",
        ),
        (
            "I suffered a fractured wrist and needed time off work.",
            "I needed hospital treatment and have ongoing physiotherapy.",
            "My property was damaged and I have repair quotes.",
        ),
        (
            "I hold your policyholder responsible and am claiming against their liability cover.",
            "A solicitor is advising me and medical reports are available.",
            "Witnesses saw the incident and have given their details.",
        ),
    ),
    Category.OTHER: (
        (
            "Strong winds during a storm blew down the garden fence.",
            "My laptop was knocked off a table and the screen cracked.",
            "A power cut lasting two days spoiled the contents of our freezer.",
            "My bicycle was damaged when a gate fell on it in high wind.",
        ),
        (
            "Six fence panels and two posts need replacing.",
            "The screen and the hinge are broken and the laptop does not turn on.",
            "All frozen food had to be thrown away.",
        ),
        (
            "A local contractor has given a quote.",
            "I have the receipts for the items involved.",
            "Photos are available on request.",
        ),
    ),
}

AMBIGUOUS_STORIES = {
    "ambiguous_water_fire": (
        "A pipe burst inside the kitchen wall overnight. The water ran down into the fuse board, "
        "which shorted and started an electrical fire. The fire damaged the kitchen ceiling and "
        "units, and the water ruined the flooring and the wall behind the cooker."
    ),
    "ambiguous_theft_collision": (
        "My {car} was taken from my driveway overnight. The police found it the next morning two "
        "miles away, where it had been driven into a lamp post. The front of the car is badly "
        "damaged and the steering lock was forced."
    ),
}

SECOND_CLAIM_STORY = (
    "Separately, my {car} was broken into on the same street the following week and the stereo "
    "was taken. I was given a different reference for that, {other_claim}, and I would like both "
    "dealt with together if possible."
)

LONG_FILLERS = (
    "I want to set out the full sequence of events so that nothing is missed.",
    "Earlier that day everything in the house had seemed normal and nobody noticed anything unusual.",
    "My neighbour came round to help and stayed for most of the afternoon.",
    "I phoned the helpline and was told to keep all receipts and take photographs of everything.",
    "Over the following days a number of tradespeople came to look at the damage and give advice.",
    "One contractor said the work could take several weeks because of the drying time needed.",
    "We have had to move some furniture into storage while the rooms are empty.",
    "I have kept a diary of every phone call and visit since the incident.",
    "The cost of temporary arrangements has been higher than I expected.",
    "I am attaching copies of the estimates I have received so far.",
    "I would appreciate a call back to discuss the next steps and the timescale.",
    "My family have been very understanding but the disruption has been considerable.",
    "The loss adjuster who visited took measurements and photographs of each room.",
    "I was asked whether anything similar had happened before, and it has not.",
    "I checked the policy wording and believe this is covered, but please confirm.",
    "A further quote is expected next week once the supplier has checked stock.",
    "Some items could be cleaned, but others will have to be replaced entirely.",
    "I have listed the damaged items separately with their approximate age and value.",
    "The work so far has been done by a firm recommended by a friend.",
    "I have tried to keep the extra costs to a minimum while things are sorted out.",
)

LIABILITY_LONG_FILLERS = (
    "I had to attend several follow-up appointments at the fracture clinic.",
    "My employer has confirmed in writing the dates I was unable to work.",
    "The physiotherapist has recommended a further course of sessions.",
    "I have kept receipts for taxis to and from my appointments.",
    "Sleeping has been difficult because of the pain, especially in the first weeks.",
    "I could not drive for some time and relied on friends and family for lifts.",
)


def describe(category: Category, rng: random.Random, car: str) -> str:
    incidents, damages, actions = STORIES[category]
    parts = [rng.choice(incidents), rng.choice(damages), rng.choice(actions)]
    return " ".join(parts).format(car=car)


def lengthen(base: str, rng: random.Random, words: int, category: Category) -> str:
    pool = LONG_FILLERS + (LIABILITY_LONG_FILLERS if category == Category.LIABILITY else ())
    sentences = [base]
    count = len(base.split())
    while count < words:
        sentence = rng.choice(pool)
        sentences.append(sentence)
        count += len(sentence.split())
    return " ".join(sentences)
