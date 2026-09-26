import requests


# ============================================================
# COUNTRY → CURRENCY MAP
# ============================================================

COUNTRY_CURRENCIES = {
    # North America
    "united states": "USD",
    "usa": "USD",
    "us": "USD",
    "america": "USD",

    "canada": "CAD",

    # Europe
    "united kingdom": "GBP",
    "uk": "GBP",
    "england": "GBP",
    "france": "EUR",
    "germany": "EUR",
    "italy": "EUR",
    "spain": "EUR",
    "portugal": "EUR",
    "ireland": "EUR",
    "netherlands": "EUR",
    "belgium": "EUR",
    "austria": "EUR",
    "finland": "EUR",
    "greece": "EUR",
    "eurozone": "EUR",

    # Asia
    "china": "CNY",
    "japan": "JPY",
    "south korea": "KRW",
    "korea": "KRW",
    "singapore": "SGD",
    "malaysia": "MYR",
    "indonesia": "IDR",
    "thailand": "THB",
    "philippines": "PHP",
    "vietnam": "VND",
    "bangladesh": "BDT",
    "pakistan": "PKR",
    "nepal": "NPR",
    "sri lanka": "LKR",

    # Middle East
    "united arab emirates": "AED",
    "uae": "AED",
    "dubai": "AED",
    "abu dhabi": "AED",

    "saudi arabia": "SAR",
    "qatar": "QAR",
    "kuwait": "KWD",
    "bahrain": "BHD",
    "oman": "OMR",
    "jordan": "JOD",
    "israel": "ILS",

    # Oceania
    "australia": "AUD",
    "new zealand": "NZD",

    # Africa
    "south africa": "ZAR",
    "nigeria": "NGN",
    "kenya": "KES",
    "ghana": "GHS",
    "egypt": "EGP",
    "morocco": "MAD",
    "tanzania": "TZS",
    "uganda": "UGX",
    "ethiopia": "ETB",

    # Other commonly encountered countries
    "switzerland": "CHF",
    "sweden": "SEK",
    "norway": "NOK",
    "denmark": "DKK",
    "poland": "PLN",
    "turkey": "TRY",
    "russia": "RUB",
    "mexico": "MXN",
    "brazil": "BRL",
    "argentina": "ARS",
    "chile": "CLP",
}


# ============================================================
# COUNTRY → CURRENCY
# ============================================================

def get_currency_for_country(country: str) -> str | None:
    """
    Return the currency code for a country.

    Example:
        USA → USD
        Germany → EUR
        Dubai → AED
    """

    if not country:
        return None

    normalized_country = country.strip().lower()

    return COUNTRY_CURRENCIES.get(normalized_country)


# ============================================================
# INR → CURRENCY CONVERSION
# ============================================================

def convert_inr_to_currency(amount_inr: float, currency: str) -> dict:
    """
    Convert an INR amount into another currency.

    Uses ExchangeRate-API Open Access.
    The service provides daily exchange rates and supports
    a wide range of international currencies.
    """

    currency = currency.upper().strip()

    if amount_inr < 0:
        return {
            "success": False,
            "error": "Amount cannot be negative.",
        }

    # INR → INR
    if currency == "INR":
        return {
            "success": True,
            "from_currency": "INR",
            "to_currency": "INR",
            "amount_inr": amount_inr,
            "exchange_rate": 1.0,
            "converted_amount": round(amount_inr, 2),
        }

    url = "https://open.er-api.com/v6/latest/INR"

    try:
        response = requests.get(
            url,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        if data.get("result") != "success":
            return {
                "success": False,
                "error": "Exchange-rate service returned an unsuccessful response.",
            }

        rates = data.get("rates", {})

        if currency not in rates:
            return {
                "success": False,
                "error": f"Currency '{currency}' is not supported.",
            }

        exchange_rate = rates[currency]

        converted_amount = amount_inr * exchange_rate

        return {
            "success": True,
            "from_currency": "INR",
            "to_currency": currency,
            "amount_inr": amount_inr,
            "exchange_rate": round(exchange_rate, 8),
            "converted_amount": round(converted_amount, 2),
            "last_update": data.get("time_last_update_utc"),
            "next_update": data.get("time_next_update_utc"),
            "provider": "ExchangeRate-API",
        }

    except requests.RequestException as error:
        return {
            "success": False,
            "error": f"Currency conversion service unavailable: {error}",
        }

    except (ValueError, TypeError, KeyError) as error:
        return {
            "success": False,
            "error": f"Unable to process currency conversion: {error}",
        }

# ============================================================
# COUNTRY → INR → LOCAL CURRENCY
# ============================================================

def convert_inr_to_country_currency(
    amount_inr: float,
    country: str,
) -> dict:
    """
    Convert an INR fee into the currency used by the student's country.

    Example:
        ₹150000 + USA
        → USD
        → converted USD amount
    """

    currency = get_currency_for_country(country)

    if not currency:
        return {
            "success": False,
            "country": country,
            "error": f"Currency for '{country}' is not configured.",
        }

    result = convert_inr_to_currency(
        amount_inr,
        currency,
    )

    result["country"] = country

    return result