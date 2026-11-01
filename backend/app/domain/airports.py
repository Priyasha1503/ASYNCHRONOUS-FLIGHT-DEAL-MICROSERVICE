"""Static airport reference data (IATA code, city, IANA timezone, coordinates).

A bounded, hand-curated set of major airports. It powers validation, local-time display, the demo
provider's route geometry and (Phase 3) origin/destination autocomplete. Real providers may return
airports outside this set; those are accepted and shown by code.
"""

import math
from dataclasses import dataclass
from zoneinfo import ZoneInfo


@dataclass(frozen=True, slots=True)
class Airport:
    iata: str
    name: str
    city: str
    country: str  # ISO 3166-1 alpha-2
    tz: str
    lat: float
    lon: float

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.tz)


_RAW: list[tuple[str, str, str, str, str, float, float]] = [
    # Europe
    ("LHR", "Heathrow", "London", "GB", "Europe/London", 51.470, -0.454),
    ("LGW", "Gatwick", "London", "GB", "Europe/London", 51.153, -0.182),
    ("MAN", "Manchester", "Manchester", "GB", "Europe/London", 53.354, -2.275),
    ("DUB", "Dublin", "Dublin", "IE", "Europe/Dublin", 53.421, -6.270),
    ("CDG", "Charles de Gaulle", "Paris", "FR", "Europe/Paris", 49.010, 2.548),
    ("ORY", "Orly", "Paris", "FR", "Europe/Paris", 48.726, 2.365),
    ("AMS", "Schiphol", "Amsterdam", "NL", "Europe/Amsterdam", 52.310, 4.768),
    ("FRA", "Frankfurt", "Frankfurt", "DE", "Europe/Berlin", 50.038, 8.562),
    ("MUC", "Munich", "Munich", "DE", "Europe/Berlin", 48.354, 11.786),
    ("BER", "Brandenburg", "Berlin", "DE", "Europe/Berlin", 52.366, 13.503),
    ("ZRH", "Zurich", "Zurich", "CH", "Europe/Zurich", 47.458, 8.548),
    ("MAD", "Barajas", "Madrid", "ES", "Europe/Madrid", 40.472, -3.561),
    ("BCN", "El Prat", "Barcelona", "ES", "Europe/Madrid", 41.297, 2.078),
    ("LIS", "Humberto Delgado", "Lisbon", "PT", "Europe/Lisbon", 38.774, -9.134),
    ("FCO", "Fiumicino", "Rome", "IT", "Europe/Rome", 41.800, 12.239),
    ("MXP", "Malpensa", "Milan", "IT", "Europe/Rome", 45.630, 8.723),
    ("VIE", "Vienna", "Vienna", "AT", "Europe/Vienna", 48.110, 16.570),
    ("CPH", "Kastrup", "Copenhagen", "DK", "Europe/Copenhagen", 55.618, 12.656),
    ("ARN", "Arlanda", "Stockholm", "SE", "Europe/Stockholm", 59.650, 17.919),
    ("IST", "Istanbul", "Istanbul", "TR", "Europe/Istanbul", 41.262, 28.742),
    ("ATH", "Athens", "Athens", "GR", "Europe/Athens", 37.936, 23.947),
    # Middle East / Africa
    ("DXB", "Dubai", "Dubai", "AE", "Asia/Dubai", 25.253, 55.365),
    ("DOH", "Hamad", "Doha", "QA", "Asia/Qatar", 25.273, 51.608),
    ("AUH", "Zayed", "Abu Dhabi", "AE", "Asia/Dubai", 24.433, 54.651),
    ("CAI", "Cairo", "Cairo", "EG", "Africa/Cairo", 30.122, 31.406),
    ("JNB", "O. R. Tambo", "Johannesburg", "ZA", "Africa/Johannesburg", -26.139, 28.246),
    ("NBO", "Jomo Kenyatta", "Nairobi", "KE", "Africa/Nairobi", -1.319, 36.928),
    # Asia / Pacific
    ("DEL", "Indira Gandhi", "Delhi", "IN", "Asia/Kolkata", 28.556, 77.100),
    ("BOM", "Chhatrapati Shivaji", "Mumbai", "IN", "Asia/Kolkata", 19.090, 72.866),
    ("BLR", "Kempegowda", "Bengaluru", "IN", "Asia/Kolkata", 13.199, 77.706),
    ("MAA", "Chennai", "Chennai", "IN", "Asia/Kolkata", 12.990, 80.169),
    ("SIN", "Changi", "Singapore", "SG", "Asia/Singapore", 1.364, 103.991),
    ("BKK", "Suvarnabhumi", "Bangkok", "TH", "Asia/Bangkok", 13.690, 100.750),
    ("KUL", "Kuala Lumpur", "Kuala Lumpur", "MY", "Asia/Kuala_Lumpur", 2.746, 101.710),
    ("HKG", "Hong Kong", "Hong Kong", "HK", "Asia/Hong_Kong", 22.308, 113.918),
    ("NRT", "Narita", "Tokyo", "JP", "Asia/Tokyo", 35.772, 140.393),
    ("HND", "Haneda", "Tokyo", "JP", "Asia/Tokyo", 35.549, 139.780),
    ("ICN", "Incheon", "Seoul", "KR", "Asia/Seoul", 37.460, 126.441),
    ("SYD", "Kingsford Smith", "Sydney", "AU", "Australia/Sydney", -33.940, 151.175),
    ("MEL", "Tullamarine", "Melbourne", "AU", "Australia/Melbourne", -37.669, 144.841),
    # Americas
    ("JFK", "John F. Kennedy", "New York", "US", "America/New_York", 40.641, -73.778),
    ("EWR", "Newark Liberty", "New York", "US", "America/New_York", 40.690, -74.174),
    ("BOS", "Logan", "Boston", "US", "America/New_York", 42.366, -71.010),
    ("IAD", "Dulles", "Washington", "US", "America/New_York", 38.953, -77.456),
    ("ATL", "Hartsfield-Jackson", "Atlanta", "US", "America/New_York", 33.641, -84.428),
    ("MIA", "Miami", "Miami", "US", "America/New_York", 25.795, -80.287),
    ("ORD", "O'Hare", "Chicago", "US", "America/Chicago", 41.974, -87.907),
    ("DFW", "Dallas/Fort Worth", "Dallas", "US", "America/Chicago", 32.900, -97.040),
    ("DEN", "Denver", "Denver", "US", "America/Denver", 39.856, -104.674),
    ("LAX", "Los Angeles", "Los Angeles", "US", "America/Los_Angeles", 33.942, -118.408),
    ("SFO", "San Francisco", "San Francisco", "US", "America/Los_Angeles", 37.621, -122.379),
    ("SEA", "Seattle-Tacoma", "Seattle", "US", "America/Los_Angeles", 47.450, -122.309),
    ("YYZ", "Pearson", "Toronto", "CA", "America/Toronto", 43.678, -79.625),
    ("YVR", "Vancouver", "Vancouver", "CA", "America/Vancouver", 49.195, -123.180),
    ("MEX", "Benito Juárez", "Mexico City", "MX", "America/Mexico_City", 19.436, -99.072),
    ("GRU", "Guarulhos", "São Paulo", "BR", "America/Sao_Paulo", -23.435, -46.473),
    ("EZE", "Ezeiza", "Buenos Aires", "AR", "America/Argentina/Buenos_Aires", -34.822, -58.536),
    # India (more cities)
    ("HYD", "Rajiv Gandhi", "Hyderabad", "IN", "Asia/Kolkata", 17.240, 78.429),
    ("CCU", "Netaji Subhas Chandra Bose", "Kolkata", "IN", "Asia/Kolkata", 22.654, 88.447),
    ("GOI", "Dabolim", "Goa", "IN", "Asia/Kolkata", 15.380, 73.831),
    ("COK", "Cochin", "Kochi", "IN", "Asia/Kolkata", 10.152, 76.402),
    ("AMD", "Sardar Vallabhbhai Patel", "Ahmedabad", "IN", "Asia/Kolkata", 23.077, 72.635),
    ("PNQ", "Pune", "Pune", "IN", "Asia/Kolkata", 18.582, 73.920),
    ("JAI", "Jaipur", "Jaipur", "IN", "Asia/Kolkata", 26.824, 75.812),
    ("LKO", "Chaudhary Charan Singh", "Lucknow", "IN", "Asia/Kolkata", 26.761, 80.889),
    ("TRV", "Thiruvananthapuram", "Thiruvananthapuram", "IN", "Asia/Kolkata", 8.482, 76.920),
    ("IXC", "Chandigarh", "Chandigarh", "IN", "Asia/Kolkata", 30.673, 76.788),
    ("GAU", "Lokpriya Gopinath Bordoloi", "Guwahati", "IN", "Asia/Kolkata", 26.106, 91.586),
    ("PAT", "Jay Prakash Narayan", "Patna", "IN", "Asia/Kolkata", 25.591, 85.088),
    ("BBI", "Biju Patnaik", "Bhubaneswar", "IN", "Asia/Kolkata", 20.244, 85.818),
    ("NAG", "Dr. Babasaheb Ambedkar", "Nagpur", "IN", "Asia/Kolkata", 21.092, 79.047),
    ("VNS", "Lal Bahadur Shastri", "Varanasi", "IN", "Asia/Kolkata", 25.452, 82.859),
    ("IXB", "Bagdogra", "Siliguri", "IN", "Asia/Kolkata", 26.681, 88.329),
    ("SXR", "Srinagar", "Srinagar", "IN", "Asia/Kolkata", 33.987, 74.774),
    ("ATQ", "Sri Guru Ram Dass Jee", "Amritsar", "IN", "Asia/Kolkata", 31.710, 74.797),
    ("IDR", "Devi Ahilya Bai Holkar", "Indore", "IN", "Asia/Kolkata", 22.722, 75.801),
    ("CCJ", "Calicut", "Kozhikode", "IN", "Asia/Kolkata", 11.137, 75.955),
    ("IXM", "Madurai", "Madurai", "IN", "Asia/Kolkata", 9.835, 78.093),
    ("VTZ", "Visakhapatnam", "Visakhapatnam", "IN", "Asia/Kolkata", 17.721, 83.224),
    ("CJB", "Coimbatore", "Coimbatore", "IN", "Asia/Kolkata", 11.030, 77.043),
    ("IXE", "Mangaluru", "Mangaluru", "IN", "Asia/Kolkata", 12.961, 74.890),
    ("BDQ", "Vadodara", "Vadodara", "IN", "Asia/Kolkata", 22.336, 73.226),
    ("RPR", "Swami Vivekananda", "Raipur", "IN", "Asia/Kolkata", 21.180, 81.739),
    ("IXR", "Birsa Munda", "Ranchi", "IN", "Asia/Kolkata", 23.314, 85.322),
    ("UDR", "Maharana Pratap", "Udaipur", "IN", "Asia/Kolkata", 24.618, 73.896),
    ("DED", "Jolly Grant", "Dehradun", "IN", "Asia/Kolkata", 30.190, 78.180),
    ("IXZ", "Veer Savarkar", "Port Blair", "IN", "Asia/Kolkata", 11.641, 92.730),
    ("TIR", "Tirupati", "Tirupati", "IN", "Asia/Kolkata", 13.633, 79.543),
    # South Asia & Middle East
    ("KTM", "Tribhuvan", "Kathmandu", "NP", "Asia/Kathmandu", 27.697, 85.359),
    ("CMB", "Bandaranaike", "Colombo", "LK", "Asia/Colombo", 7.180, 79.884),
    ("DAC", "Hazrat Shahjalal", "Dhaka", "BD", "Asia/Dhaka", 23.843, 90.398),
    ("MLE", "Velana", "Malé", "MV", "Indian/Maldives", 4.191, 73.529),
    ("MCT", "Muscat", "Muscat", "OM", "Asia/Muscat", 23.593, 58.284),
    ("BAH", "Bahrain", "Manama", "BH", "Asia/Bahrain", 26.271, 50.634),
    ("KWI", "Kuwait", "Kuwait City", "KW", "Asia/Kuwait", 29.227, 47.969),
    ("RUH", "King Khalid", "Riyadh", "SA", "Asia/Riyadh", 24.958, 46.699),
    ("JED", "King Abdulaziz", "Jeddah", "SA", "Asia/Riyadh", 21.680, 39.157),
    ("SHJ", "Sharjah", "Sharjah", "AE", "Asia/Dubai", 25.329, 55.517),
    # East & Southeast Asia
    ("PEK", "Capital", "Beijing", "CN", "Asia/Shanghai", 40.080, 116.584),
    ("PVG", "Pudong", "Shanghai", "CN", "Asia/Shanghai", 31.143, 121.805),
    ("CAN", "Baiyun", "Guangzhou", "CN", "Asia/Shanghai", 23.392, 113.299),
    ("TPE", "Taoyuan", "Taipei", "TW", "Asia/Taipei", 25.077, 121.233),
    ("MNL", "Ninoy Aquino", "Manila", "PH", "Asia/Manila", 14.509, 121.020),
    ("CGK", "Soekarno-Hatta", "Jakarta", "ID", "Asia/Jakarta", -6.126, 106.656),
    ("DPS", "Ngurah Rai", "Bali", "ID", "Asia/Makassar", -8.748, 115.167),
    ("SGN", "Tan Son Nhat", "Ho Chi Minh City", "VN", "Asia/Ho_Chi_Minh", 10.819, 106.652),
    ("HAN", "Noi Bai", "Hanoi", "VN", "Asia/Bangkok", 21.221, 105.807),
    ("HKT", "Phuket", "Phuket", "TH", "Asia/Bangkok", 8.113, 98.317),
    ("KIX", "Kansai", "Osaka", "JP", "Asia/Tokyo", 34.427, 135.244),
    # Europe, Oceania, Americas, Africa
    ("EDI", "Edinburgh", "Edinburgh", "GB", "Europe/London", 55.950, -3.373),
    ("PRG", "Václav Havel", "Prague", "CZ", "Europe/Prague", 50.101, 14.260),
    ("WAW", "Chopin", "Warsaw", "PL", "Europe/Warsaw", 52.166, 20.967),
    ("BRU", "Brussels", "Brussels", "BE", "Europe/Brussels", 50.901, 4.484),
    ("HEL", "Helsinki-Vantaa", "Helsinki", "FI", "Europe/Helsinki", 60.317, 24.963),
    ("OSL", "Gardermoen", "Oslo", "NO", "Europe/Oslo", 60.194, 11.100),
    ("AKL", "Auckland", "Auckland", "NZ", "Pacific/Auckland", -37.008, 174.785),
    ("PER", "Perth", "Perth", "AU", "Australia/Perth", -31.940, 115.967),
    ("BNE", "Brisbane", "Brisbane", "AU", "Australia/Brisbane", -27.384, 153.117),
    ("LAS", "Harry Reid", "Las Vegas", "US", "America/Los_Angeles", 36.084, -115.154),
    ("IAH", "George Bush", "Houston", "US", "America/Chicago", 29.990, -95.337),
    ("YUL", "Trudeau", "Montreal", "CA", "America/Toronto", 45.470, -73.741),
    ("BOG", "El Dorado", "Bogotá", "CO", "America/Bogota", 4.702, -74.147),
    ("LIM", "Jorge Chávez", "Lima", "PE", "America/Lima", -12.022, -77.114),
    ("CPT", "Cape Town", "Cape Town", "ZA", "Africa/Johannesburg", -33.965, 18.602),
    ("ADD", "Bole", "Addis Ababa", "ET", "Africa/Addis_Ababa", 8.978, 38.799),
    ("LOS", "Murtala Muhammed", "Lagos", "NG", "Africa/Lagos", 6.577, 3.321),
    ("CMN", "Mohammed V", "Casablanca", "MA", "Africa/Casablanca", 33.367, -7.590),
]

AIRPORTS: dict[str, Airport] = {r[0]: Airport(*r) for r in _RAW}

# Airports that share a metro area; used for the "nearby airports" option.
METRO_GROUPS: list[frozenset[str]] = [
    frozenset({"LHR", "LGW"}),
    frozenset({"CDG", "ORY"}),
    frozenset({"NRT", "HND"}),
    frozenset({"JFK", "EWR"}),
    frozenset({"DXB", "AUH"}),
]


def get_airport(code: str) -> Airport | None:
    return AIRPORTS.get(code.upper())


def nearby(code: str) -> frozenset[str]:
    """Other airports in the same metro area (excluding `code` itself)."""
    code = code.upper()
    for group in METRO_GROUPS:
        if code in group:
            return group - {code}
    return frozenset()


def distance_km(a: Airport, b: Airport) -> float:
    """Great-circle distance (haversine)."""
    r = 6371.0
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp, dl = p2 - p1, math.radians(b.lon - a.lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))
