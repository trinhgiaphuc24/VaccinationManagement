import csv
import json
import os
import re
import logging
import requests
from typing import Any, Text, Dict, List, Optional
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, UserUtteranceReverted, AllSlotsReset
from rasa_sdk.forms import FormValidationAction
from functools import lru_cache
from fuzzywuzzy import process
from pyvi import ViTokenizer

logger = logging.getLogger(__name__)

DJANGO_API_BASE_URL = "http://192.168.1.12:8000/"

# Load vaccine_data.json for side effects and age ranges
def load_vaccine_data(file_path: str = "vaccine_data.json") -> Dict:
    try:
        file_path = os.path.join(os.path.dirname(__file__), file_path)
        logger.debug(f"Loading vaccine_data.json from: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for vaccine in data:
            if isinstance(data[vaccine]["side_effects"], str):
                data[vaccine]["side_effects"] = [
                    effect.strip() for effect in data[vaccine]["side_effects"].split(",")
                ]
        logger.debug(f"Loaded vaccines: {list(data.keys())}")
        return data
    except Exception as e:
        logger.error(f"Error loading vaccine_data.json: {str(e)}")
        return {}

# Static data for fallback and non-API fields
VACCINE_STATIC_DATA = {
    "Infanrix Hexa": {"description": "Vaccine 6 trong 1, phòng bạch hầu, uốn ván, ho gà, viêm gan B, bại liệt, Hib.",
                      "origin": "Bỉ", "price": 1015000},
    "Hexaxim": {"description": "Vaccine 6 trong 1, phòng bạch hầu, uốn ván, ho gà, viêm gan B, bại liệt, Hib.",
                "origin": "Pháp", "price": 1050000},
    "Rotateq": {"description": "Phòng tiêu chảy do rotavirus.", "origin": "Mỹ", "price": 650000},
    "Rotarix": {"description": "Phòng tiêu chảy do rotavirus.", "origin": "Bỉ", "price": 620000},
    "Rotavin": {"description": "Phòng tiêu chảy do rotavirus.", "origin": "Việt Nam", "price": 600000},
    "Synflorix": {"description": "Phòng các bệnh do phế cầu khuẩn.", "origin": "Bỉ", "price": 1045000},
    "Prevenar 13": {"description": "Phòng các bệnh do phế cầu khuẩn.", "origin": "Mỹ", "price": 1350000},
    "Pneumovax 23": {"description": "Phòng các bệnh do phế cầu khuẩn.", "origin": "Mỹ", "price": 950000},
    "Gardasil A": {"description": "Phòng ung thư cổ tử cung và các bệnh do HPV.", "origin": "Mỹ", "price": 1800000},
    "Gardasil B": {"description": "Phòng ung thư cổ tử cung và các bệnh do HPV.", "origin": "Mỹ", "price": 1800000},
    "Vaxigrip Tetra": {"description": "Phòng cúm.", "origin": "Pháp", "price": 350000},
    "Varivax": {"description": "Phòng thủy đậu.", "origin": "Mỹ", "price": 700000},
    "Boostrix": {"description": "Phòng bạch hầu, ho gà, uốn ván.", "origin": "Bỉ", "price": 600000},
    "Varilrix": {"description": "Phòng thủy đậu.", "origin": "Bỉ", "price": 720000},
    "Influvac Tetra": {"description": "Phòng cúm.", "origin": "Hà Lan", "price": 340000},
    "GC Flu Quadrivalent": {"description": "Phòng cúm.", "origin": "Hàn Quốc", "price": 330000},
    "Ivacflu-S": {"description": "Phòng cúm.", "origin": "Việt Nam", "price": 300000},
    "BCG": {"description": "Phòng lao.", "origin": "Việt Nam", "price": 100000},
    "Gene Hbvax A": {"description": "Phòng viêm gan B.", "origin": "Việt Nam", "price": 150000},
    "Heberbiovac A": {"description": "Phòng viêm gan B.", "origin": "Cuba", "price": 160000},
    "Gene Hbvax B": {"description": "Phòng viêm gan B.", "origin": "Việt Nam", "price": 150000},
    "Heberbiovac B": {"description": "Phòng viêm gan B.", "origin": "Cuba", "price": 160000},
    "MVVac A": {"description": "Phòng sởi, quai bị, rubella.", "origin": "Việt Nam", "price": 200000},
    "MVVac B": {"description": "Phòng sởi, quai bị, rubella.", "origin": "Việt Nam", "price": 200000},
    "MMR II": {"description": "Phòng sởi, quai bị, rubella.", "origin": "Mỹ", "price": 250000},
    "Priorix": {"description": "Phòng sởi, quai bị, rubella.", "origin": "Bỉ", "price": 240000},
    "Imojev": {"description": "Phòng viêm não Nhật Bản.", "origin": "Thái Lan", "price": 400000},
    "Jeev": {"description": "Phòng viêm não Nhật Bản.", "origin": "Ấn Độ", "price": 380000},
    "Jevax": {"description": "Phòng viêm não Nhật Bản.", "origin": "Việt Nam", "price": 350000},
    "Verorab A": {"description": "Phòng dại.", "origin": "Pháp", "price": 300000},
    "Verorab B": {"description": "Phòng dại.", "origin": "Ấn Độ", "price": 280000},
    "Abhayrab A": {"description": "Phòng dại.", "origin": "Pháp", "price": 300000},
    "Abhayrab B": {"description": "Phòng dại.", "origin": "Ấn Độ", "price": 280000},
    "Adacel": {"description": "Phòng bạch hầu, ho gà, uốn ván.", "origin": "Canada", "price": 550000},
    "Tetraxim": {"description": "Phòng bạch hầu, ho gà, uốn ván, bại liệt.", "origin": "Pháp", "price": 500000},
    "Uốn ván, bạch hầu hấp phụ A": {"description": "Phòng uốn ván, bạch hầu.", "origin": "Việt Nam", "price": 120000},
    "Uốn ván, bạch hầu hấp phụ B": {"description": "Phòng uốn ván, bạch hầu.", "origin": "Việt Nam", "price": 120000},
    "Twinrix": {"description": "Phòng viêm gan A và B.", "origin": "Bỉ", "price": 800000},
    "Havax": {"description": "Phòng viêm gan A.", "origin": "Việt Nam", "price": 400000},
    "Avaxim": {"description": "Phòng viêm gan A.", "origin": "Pháp", "price": 450000}
}

# Load vaccine_data.json and merge with VACCINE_STATIC_DATA
VACCINE_JSON_DATA = load_vaccine_data()
for vaccine in VACCINE_JSON_DATA:
    if vaccine != "default" and vaccine in VACCINE_STATIC_DATA:
        VACCINE_STATIC_DATA[vaccine].update({
            "age_range": VACCINE_JSON_DATA[vaccine]["age_range"],
            "side_effects": VACCINE_JSON_DATA[vaccine]["side_effects"]
        })

# Synonyms for vaccine names
SYNONYMS = {
    "6 trong 1": ["Infanrix Hexa", "Hexaxim"],
    "vaccine phế cầu": ["Synflorix", "Prevenar 13", "Pneumovax 23"],
    "vaccine viêm gan B": ["Gene Hbvax A", "Heberbiovac A", "Gene Hbvax B", "Heberbiovac B"],
    "vaccine sởi": ["MVVac A", "MVVac B", "MMR II", "Priorix"],
    "vaccine thủy đậu": ["Varivax", "Varilrix"],
    "vaccine cúm": ["Vaxigrip Tetra", "Influvac Tetra", "GC Flu Quadrivalent", "Ivacflu-S"],
    "vaccine viêm não Nhật Bản": ["Imojev", "Jeev", "Jevax"],
    "vaccine dại": ["Verorab A", "Verorab B", "Abhayrab A", "Abhayrab B"],
    "vaccine uốn ván bạch hầu": ["Uốn ván, bạch hầu hấp phụ A", "Uốn ván, bạch hầu hấp phụ B"],
    "vaccine HPV": ["Gardasil A", "Gardasil B"],
    "phế cầu người lớn": ["Pneumovax 23"]
}

# Vaccination schedule by age
VACCINATION_SCHEDULE = {
    "trẻ sơ sinh": ["BCG", "Gene Hbvax A"],
    "2 tháng": ["Infanrix Hexa", "Hexaxim", "Prevenar 13", "Rotateq"],
    "6 tháng": ["Infanrix Hexa", "Hexaxim", "Vaxigrip Tetra", "Rotarix"],
    "12 tháng": ["Varivax", "Prevenar 13", "MMR II"],
    "người lớn": ["Vaxigrip Tetra", "Pneumovax 23", "Twinrix", "Gardasil A"]
}

# Symptoms to vaccines mapping
SYMPTOM_TO_VACCINE = {
    "sốt": ["Infanrix Hexa", "Hexaxim", "Vaxigrip Tetra", "Prevenar 13", "Rotateq"],
    "sưng": ["Infanrix Hexa", "Hexaxim", "Prevenar 13", "Pneumovax 23"],
    "quấy khóc": ["Infanrix Hexa", "Hexaxim", "Synflorix"],
    "mệt mỏi": ["Vaxigrip Tetra", "Boostrix"],
    "đau": ["Infanrix Hexa", "Hexaxim", "Boostrix"],
    "chán ăn": ["Prevenar 13", "Synflorix", "Rotateq"],
    "sốt nhẹ": ["Infanrix Hexa", "Hexaxim", "Vaxigrip Tetra"],
    "đau cơ": ["Gardasil A", "Gardasil B"],
    "nhức đầu": ["Gardasil A", "Gardasil B"],
    "nổi hạch": ["BCG"]
}

AGE_SYNONYMS = {
    "trẻ sơ_sinh": "trẻ sơ sinh",
    "tre so sinh": "trẻ sơ sinh",
    "trẻ sơsinh": "trẻ sơ sinh",
    "trẻ mới sinh": "trẻ sơ sinh",
    "sơ sinh": "trẻ sơ sinh",
    "2 thang": "2 tháng",
    "6 thang": "6 tháng",
    "12 thang": "12 tháng",
    "nguoi lon": "người lớn",
    "người_lớn": "người lớn",
    "nguoi_lon": "người lớn",
    "ng lon": "người lớn",
    "người lớn tuổi": "người lớn",
    "nguoi lon tuoi": "người lớn",
    "ng lon tuoi": "người lớn"
}

def normalize_input(value: Text) -> Text:
    if not value:
        return ""
    # Apply synonym mapping before tokenization
    value = value.lower().strip()
    value = AGE_SYNONYMS.get(value, value)
    # Tokenize and normalize Vietnamese text
    value = ViTokenizer.tokenize(value)
    corrections = {
        "vắc xin": "vaccine",
        "hexxim": "hexaxim",
        "infanrixhexa": "infanrix hexa",
        "6in1": "6 trong 1",
        "vaxigrip": "vaxigrip tetra",
        "prevenar": "prevenar 13",
        "pneumovax": "pneumovax 23",
        "gardasil": "gardasil a",
        "varivaxx": "varivax",
        "boostrixx": "boostrix"
    }
    for wrong, correct in corrections.items():
        value = value.replace(wrong, correct)
    value = re.sub(r'\s+', ' ', value.strip())
    # Apply synonym mapping again after tokenization
    return AGE_SYNONYMS.get(value, value)

def resolve_synonym(vaccine_name: Text) -> Text:
    if not vaccine_name:
        return ""
    vaccine_name = normalize_input(vaccine_name)

    # Check synonyms first
    for synonym, canonical_names in SYNONYMS.items():
        if vaccine_name == normalize_input(synonym):
            return canonical_names[0]
        for canonical in canonical_names:
            if vaccine_name == canonical.lower():
                return canonical

    # Check directly in VACCINE_STATIC_DATA
    for key in VACCINE_STATIC_DATA:
        if vaccine_name == key.lower():
            return key

    # Use fuzzy matching for non-standard inputs
    all_vaccines = list(VACCINE_STATIC_DATA.keys()) + list(SYNONYMS.keys())
    match = process.extractOne(vaccine_name, all_vaccines, score_cutoff=80)
    if match:
        matched_name = match[0]
        for synonym, canonical_names in SYNONYMS.items():
            if matched_name == synonym:
                return canonical_names[0]
        return matched_name

    return vaccine_name.title()

@lru_cache(maxsize=100)
def fetch_vaccine_from_api(vaccine_name: Text) -> Dict[Text, Any]:
    normalized_name = normalize_input(vaccine_name)
    try:
        response = requests.get(f"{DJANGO_API_BASE_URL}vaccines/?q={normalized_name}", timeout=5)
        response.raise_for_status()
        vaccines = response.json().get("results", [])
        for vaccine in vaccines:
            if normalize_input(vaccine.get("name", "")) == normalized_name:
                description = vaccine.get("description", "")
                if "Infanrix Hexa" in description and vaccine["name"] != "Infanrix Hexa":
                    description = VACCINE_STATIC_DATA.get(vaccine["name"], {}).get("description", "Không rõ")
                return {
                    "description": description,
                    "price": vaccine.get("price", 0),
                    "origin": vaccine.get("country_produce", {}).get("name",
                                                                     VACCINE_STATIC_DATA.get(vaccine_name, {}).get(
                                                                         "origin", "Không rõ")),
                    "image": vaccine.get("imgUrl", "")
                }
        if vaccine_name in VACCINE_STATIC_DATA:
            return {
                "description": VACCINE_STATIC_DATA[vaccine_name].get("description", "Không rõ"),
                "price": VACCINE_STATIC_DATA[vaccine_name].get("price", 0),
                "origin": VACCINE_STATIC_DATA[vaccine_name].get("origin", "Không rõ"),
                "image": ""
            }
        return {}
    except requests.RequestException as e:
        logger.error(f"Error fetching vaccine '{vaccine_name}': {str(e)}")
        if vaccine_name in VACCINE_STATIC_DATA:
            return {
                "description": VACCINE_STATIC_DATA[vaccine_name].get("description", "Không rõ"),
                "price": VACCINE_STATIC_DATA[vaccine_name].get("price", 0),
                "origin": VACCINE_STATIC_DATA[vaccine_name].get("origin", "Không rõ"),
                "image": ""
            }
        return {}

class ValidatePriceForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_price_form"

    async def validate_vaccine_name(
            self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> Dict[Text, Any]:
        if not slot_value:
            dispatcher.utter_message(response="utter_ask_price_form_vaccine_name")
            return {"vaccine_name": None}

        vaccine_name = resolve_synonym(slot_value)
        vaccine = fetch_vaccine_from_api(vaccine_name)
        if vaccine.get("description", "Không rõ") != "Không rõ" or vaccine_name in VACCINE_STATIC_DATA:
            return {"vaccine_name": vaccine_name}
        else:
            valid_vaccines = list(VACCINE_STATIC_DATA.keys())[:5]
            dispatcher.utter_message(
                text=f"⚠️ Không tìm thấy vaccine '{vaccine_name}'. Vui lòng chọn vaccine khác:",
                buttons=[{"title": v, "payload": v} for v in valid_vaccines]
            )
            return {"vaccine_name": None}

class ActionGetVaccinePrice(Action):
    def name(self) -> Text:
        return "action_get_vaccine_price"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        vaccine_name = tracker.get_slot("vaccine_name")
        if not vaccine_name:
            dispatcher.utter_message(response="utter_ask_price_form_vaccine_name")
            return []

        vaccine_name = resolve_synonym(vaccine_name)
        vaccine = fetch_vaccine_from_api(vaccine_name)
        price = vaccine.get("price", 0)

        if price:
            msg = (
                f"💰 **Giá {vaccine_name}**: {price:,} VND\n"
                f"- **Lưu ý**: Giá có thể thay đổi, liên hệ cơ sở y tế để xác nhận.\n"
                f"- **Nguồn**: https://moh.gov.vn"
            )
            dispatcher.utter_message(
                text=msg,
                buttons=[
                    {"title": "Thông tin vaccine",
                     "payload": f"/ask_vaccine_info{{\"vaccine_name\": \"{vaccine_name}\"}}"},
                    {"title": "Địa điểm tiêm",
                     "payload": f"/ask_vaccination_location{{\"vaccine_name\": \"{vaccine_name}\"}}"}
                ]
            )
        else:
            valid_vaccines = list(VACCINE_STATIC_DATA.keys())[:5]
            dispatcher.utter_message(
                text=f"⚠️ Không tìm thấy giá cho '{vaccine_name}'. Vui lòng chọn vaccine khác:",
                buttons=[{"title": v, "payload": v} for v in valid_vaccines]
            )
        return [SlotSet("vaccine_name", vaccine_name)]

class ActionGetVaccineInfo(Action):
    def name(self) -> Text:
        return "action_get_vaccine_info"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        vaccine_name = tracker.get_slot("vaccine_name")
        if not vaccine_name:
            dispatcher.utter_message(response="utter_ask_vaccine_form_vaccine_name")
            return []

        vaccine_name = resolve_synonym(vaccine_name)
        vaccine = fetch_vaccine_from_api(vaccine_name)
        description = vaccine.get("description", "Không rõ")
        origin = vaccine.get("origin", "Không rõ")
        price = vaccine.get("price", 0)

        if description != "Không rõ":
            msg = (
                f"💉 **{vaccine_name}**:\n"
                f"- **Mô tả**: {description}\n"
                f"- **Nguồn gốc**: {origin}\n"
                f"- **Giá tham khảo**: {price:,} VND\n"
                f"- **Lưu ý**: Vui lòng tham khảo bác sĩ hoặc https://moh.gov.vn"
            )
            dispatcher.utter_message(
                text=msg,
                buttons=[
                    {"title": "Tác dụng phụ", "payload": f"/ask_side_effects{{\"vaccine_name\": \"{vaccine_name}\"}}"},
                    {"title": "Độ tuổi tiêm",
                     "payload": f"/ask_vaccination_age{{\"vaccine_name\": \"{vaccine_name}\"}}"}
                ]
            )
        else:
            valid_vaccines = list(VACCINE_STATIC_DATA.keys())[:5]
            dispatcher.utter_message(
                text=f"⚠️ Không tìm thấy thông tin cho '{vaccine_name}'. Vui lòng chọn vaccine khác:",
                buttons=[{"title": v, "payload": v} for v in valid_vaccines]
            )
        return [SlotSet("vaccine_name", vaccine_name)]

class ActionGetVaccinationAge(Action):
    def name(self) -> Text:
        return "action_get_vaccination_age"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        vaccine_name = tracker.get_slot("vaccine_name")
        age = tracker.get_slot("age")
        if not vaccine_name:
            dispatcher.utter_message(response="utter_request_vaccine_name")
            return []

        vaccine_name = resolve_synonym(vaccine_name)
        age_range = VACCINE_STATIC_DATA.get(vaccine_name, {}).get("age_range", "Không rõ")
        if age_range == "Không rõ":
            age_range = VACCINE_JSON_DATA.get("default", {}).get("age_range", "Không rõ")

        if age_range != "Không rõ":
            msg = (
                f"🎂 **Độ tuổi tiêm {vaccine_name}**: {age_range}\n"
                f"- **Lưu ý**: Tham khảo bác sĩ để xác nhận.\n"
                f"- **Nguồn**: https://moh.gov.vn"
            )
            if age:
                msg += f"\n- **Đối với {age}**: Vui lòng kiểm tra với bác sĩ để đảm bảo phù hợp."
            dispatcher.utter_message(
                text=msg,
                buttons=[
                    {"title": "Thông tin vaccine",
                     "payload": f"/ask_vaccine_info{{\"vaccine_name\": \"{vaccine_name}\"}}"},
                    {"title": "Tác dụng phụ", "payload": f"/ask_side_effects{{\"vaccine_name\": \"{vaccine_name}\"}}"}
                ]
            )
        else:
            valid_vaccines = list(VACCINE_STATIC_DATA.keys())[:5]
            dispatcher.utter_message(
                text=f"⚠️ Không tìm thấy thông tin độ tuổi cho '{vaccine_name}'. Vui lòng chọn vaccine khác:",
                buttons=[{"title": v, "payload": v} for v in valid_vaccines]
            )
        return [SlotSet("vaccine_name", vaccine_name), SlotSet("age", age)]

class ActionGetSideEffects(Action):
    def name(self) -> Text:
        return "action_get_side_effects"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        vaccine_name = tracker.get_slot("vaccine_name")
        symptom = tracker.get_slot("symptom")
        if not vaccine_name:
            dispatcher.utter_message(response="utter_ask_side_effects_form_vaccine_name")
            return []

        vaccine_name = resolve_synonym(vaccine_name)
        side_effects = VACCINE_STATIC_DATA.get(vaccine_name, {}).get("side_effects", ["Không rõ"])

        if side_effects != ["Không rõ"]:
            msg = (
                f"⚠️ **Phản ứng phụ của {vaccine_name}**: {', '.join(side_effects)}\n"
                f"- **Hướng dẫn**: Nếu triệu chứng kéo dài, liên hệ bác sĩ.\n"
                f"- **Nguồn**: https://moh.gov.vn"
            )
            if symptom and symptom.lower() != "bỏ qua":
                msg += f"\n- Triệu chứng '{symptom}': Nếu nghiêm trọng, liên hệ bác sĩ."
            dispatcher.utter_message(
                text=msg,
                buttons=[
                    {"title": "Theo dõi sau tiêm",
                     "payload": f"/ask_post_vaccination_monitoring{{\"vaccine_name\": \"{vaccine_name}\"}}"}
                ]
            )
        else:
            valid_vaccines = list(VACCINE_STATIC_DATA.keys())[:5]
            dispatcher.utter_message(
                text=f"⚠️ Không tìm thấy tác dụng phụ cho '{vaccine_name}'. Vui lòng chọn vaccine khác:",
                buttons=[{"title": v, "payload": v} for v in valid_vaccines]
            )
        return [SlotSet("vaccine_name", vaccine_name), SlotSet("symptom", symptom)]

class ActionGetSideEffectsBySymptom(Action):
    def name(self) -> Text:
        return "action_get_side_effects_by_symptom"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        symptom = tracker.get_slot("symptom")
        if not symptom or symptom.lower() == "bỏ qua":
            dispatcher.utter_message(response="utter_request_symptom")
            return []

        symptom = normalize_input(symptom)
        vaccines = SYMPTOM_TO_VACCINE.get(symptom, [])
        if vaccines:
            msg = (
                f"🚨 **Triệu chứng '{symptom}'** có thể liên quan đến: {', '.join(vaccines)}.\n"
                f"- **Hướng dẫn**: Theo dõi 24-48 giờ, liên hệ bác sĩ nếu nghiêm trọng.\n"
                f"- **Nguồn**: https://moh.gov.vn"
            )
            dispatcher.utter_message(text=msg)
        else:
            dispatcher.utter_message(
                text=f"⚠️ Không tìm thấy vaccine liên quan đến triệu chứng '{symptom}'. Vui lòng kiểm tra lại."
            )
        return [SlotSet("symptom", symptom)]

class ActionGetVaccinationScheduleByAge(Action):
    def name(self) -> Text:
        return "action_get_vaccination_schedule_by_age"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        age = tracker.get_slot("age")
        logger.debug(f"Raw age slot: {age}")
        if not age:
            logger.debug("No age slot provided")
            dispatcher.utter_message(response="utter_ask_schedule_form_age")
            return []

        age = normalize_input(age)
        logger.debug(f"Normalized age: {age}")
        schedule = VACCINATION_SCHEDULE.get(age, [])

        # Check Django API if static data is empty
        if not schedule:
            logger.debug(f"No schedule found in static data for age: {age}, trying API")
            try:
                response = requests.get(f"{DJANGO_API_BASE_URL}schedules/?age={age}", timeout=5)
                response.raise_for_status()
                api_schedules = response.json().get("results", [])
                schedule = [s["vaccine_name"] for s in api_schedules]
                logger.debug(f"API returned schedules: {schedule}")
            except requests.RequestException as e:
                logger.error(f"Error fetching schedule for age '{age}': {str(e)}")

        if schedule:
            msg = (
                f"📅 **Lịch tiêm cho {age}**:\n"
                f"- Vaccine: {', '.join(schedule)}\n"
                f"- **Lưu ý**: Tham khảo bác sĩ để xác nhận.\n"
                f"- **Nguồn**: https://moh.gov.vn"
            )
            dispatcher.utter_message(text=msg)
        else:
            valid_ages = list(VACCINATION_SCHEDULE.keys())[:5]
            logger.debug(f"No schedule found for age: {age}, suggesting valid ages: {valid_ages}")
            dispatcher.utter_message(
                text=(
                    f"⚠️ Không tìm thấy lịch tiêm cho độ tuổi '{age}'. "
                    f"Vui lòng thử một trong các độ tuổi sau: {', '.join(valid_ages)}."
                ),
                buttons=[{"title": a, "payload": f"/ask_vaccination_schedule_by_age{{\"age\": \"{a}\"}}"} for a in valid_ages]
            )
        return [SlotSet("age", age)]

class ActionShowPreVaccinationPreparation(Action):
    def name(self) -> Text:
        return "action_show_pre_vaccination_preparation"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        vaccine_name = tracker.get_slot("vaccine_name")
        age = tracker.get_slot("age")
        msg = "Trước khi tiêm, hãy đảm bảo trẻ khỏe mạnh, không sốt, và đã ăn uống đầy đủ. Tham khảo bác sĩ nếu trẻ có bệnh nền."
        if vaccine_name:
            msg += f"\n- **Vaccine {vaccine_name}**: Kiểm tra lịch sử tiêm chủng để đảm bảo đúng liều."
        if age:
            msg += f"\n- **Độ tuổi {age}**: Đảm bảo trẻ phù hợp với vaccine theo độ tuổi."
        dispatcher.utter_message(text=msg)
        return []

class ActionShowPostVaccinationMonitoring(Action):
    def name(self) -> Text:
        return "action_show_post_vaccination_monitoring"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        vaccine_name = tracker.get_slot("vaccine_name")
        symptom = tracker.get_slot("symptom")
        msg = "Sau tiêm, theo dõi trẻ trong 24-48 giờ. Ghi nhận các triệu chứng như sốt, sưng, hoặc quấy khóc. Liên hệ bác sĩ nếu bất thường."
        if vaccine_name:
            msg += f"\n- **Vaccine {vaccine_name}**: Theo dõi các phản ứng phụ đặc trưng của vaccine."
        if symptom:
            msg += f"\n- **Triệu chứng {symptom}**: Nếu kéo dài hoặc nghiêm trọng, liên hệ bác sĩ ngay."
        dispatcher.utter_message(text=msg)
        return []

class ActionGetVaccinationLocation(Action):
    def name(self) -> Text:
        return "action_get_vaccination_location"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        vaccine_name = tracker.get_slot("vaccine_name")
        try:
            response = requests.get(f"{DJANGO_API_BASE_URL}health-centers/", timeout=5)
            response.raise_for_status()
            locations = response.json().get("results", [])
            if locations:
                message = self._format_multiple_locations(locations, vaccine_name)
                dispatcher.utter_message(text=message)
            else:
                dispatcher.utter_message(text="⚠️ Hiện tại không có địa điểm tiêm nào trong hệ thống.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching health centers: {str(e)}")
            dispatcher.utter_message(
                text="⚠️ Không thể kết nối đến danh sách địa điểm tiêm. Vui lòng thử lại sau hoặc kiểm tra kết nối mạng."
            )
        return []

    def _format_multiple_locations(self, locations: List[Dict], vaccine_name: Optional[Text] = None) -> Text:
        vaccine_info = f" {vaccine_name}" if vaccine_name else ""
        message = f"📍 Dưới đây là các địa điểm tiêm{vaccine_info} bạn có thể tham khảo:\n\n"
        for i, loc in enumerate(locations[:5], 1):
            message += (
                f"{i}. **{loc['name']}**\n"
                f"   - Địa chỉ: {loc['address']}\n\n"
            )
        message += "📞 Vui lòng liên hệ trực tiếp các trung tâm để biết tình trạng vaccine hiện tại."
        return message

class ActionDefaultFallback(Action):
    def name(self) -> Text:
        return "action_default_fallback"

    def run(
            self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(response="utter_default_fallback")
        return [UserUtteranceReverted()]

class ActionBotChallenge(Action):
    def name(self) -> Text:
        return "action_bot_challenge"

    def run(
            self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(response="utter_bot_challenge")
        return []

class ActionEvaluateChatbot(Action):
    def name(self) -> Text:
        return "action_evaluate_chatbot"

    def run(
            self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        user_input = tracker.latest_message.get("text", "").lower()
        if "hữu ích" in user_input or "tốt" in user_input or "tuyệt vời" in user_input:
            dispatcher.utter_message(text="Cảm ơn bạn! Tôi rất vui được giúp đỡ. 😊")
        else:
            dispatcher.utter_message(
                text="Xin lỗi nếu tôi chưa đáp ứng mong đợi. Bạn có thể nói rõ hơn để tôi cải thiện không?")
        return []

class ActionOutOfScope(Action):
    def name(self) -> Text:
        return "action_out_of_scope"

    def run(
            self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        user_input = tracker.latest_message.get("text", "")
        intent = tracker.latest_message.get("intent", {}).get("name", "unknown")
        entities = tracker.latest_message.get("entities", [])
        timestamp = tracker.latest_message.get("timestamp", "")

        file_path = os.path.join(os.path.dirname(__file__), "out_of_scope_queries.csv")
        file_exists = os.path.isfile(file_path)

        related_intents = ["ask_vaccine_for_new_disease", "ask_vaccine_for_special_condition"]
        related_keywords = [
            r"vaccine", r"vắc[-\s]?xin", r"tiêm", r"bệnh", r"phòng", r"viêm", r"virus",
            r"cúm", r"sởi", r"uốn ván", r"bạch hầu", r"phế cầu", r"hpv", r"thủy đậu"
        ]
        is_related = (
                intent in related_intents or
                any(re.search(keyword, user_input.lower(), re.IGNORECASE) for keyword in related_keywords)
        )

        if not is_related:
            logger.info(f"Skipping unrelated out-of-scope query: {user_input}")
            dispatcher.utter_message(response="utter_out_of_scope")
            return [UserUtteranceReverted()]

        is_duplicate = False
        if file_exists:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    next(reader, None)
                    for row in reader:
                        if row and row[0] == user_input:
                            is_duplicate = True
                            break
                if is_duplicate:
                    logger.info(f"Duplicate out-of-scope query found, not saving: {user_input}")
            except Exception as e:
                logger.error(f"Error reading CSV file {file_path} for duplicate check: {str(e)}")

        if not is_duplicate:
            try:
                with open(file_path, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    if not file_exists:
                        writer.writerow(["user_input", "intent", "entities", "timestamp"])
                    writer.writerow([user_input, intent, str(entities), timestamp])
                logger.info(f"Saved out-of-scope query to CSV: {user_input}")
            except Exception as e:
                logger.error(f"Error writing to CSV file {file_path}: {str(e)}")

        dispatcher.utter_message(response="utter_out_of_scope")
        return [UserUtteranceReverted()]

class ActionGetVaccineForDisease(Action):
    def name(self) -> Text:
        return "action_get_vaccine_for_disease"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        disease = tracker.get_slot("disease")
        if not disease:
            dispatcher.utter_message(
                text="Xin lỗi, tôi không nhận diện được bệnh bạn đang hỏi. Vui lòng cung cấp tên bệnh cụ thể, ví dụ: viêm gan C."
            )
            return []

        disease = normalize_input(disease)
        disease_vaccine_info = {
            "viêm gan c": "Hiện tại, chưa có vaccine phòng viêm gan C. Bạn nên tham khảo bác sĩ về các biện pháp phòng ngừa như tránh tiếp xúc với máu nhiễm bệnh hoặc sử dụng bao cao su khi quan hệ tình dục.",
            "zika": "Hiện không có vaccine phòng Zika được phê duyệt rộng rãi. WHO khuyến nghị tránh muỗi đốt và tham khảo ý kiến bác sĩ nếu bạn ở khu vực có nguy cơ cao.",
            "dengue": "Vaccine phòng sốt xuất huyết (Dengvaxia) có sẵn ở một số quốc gia, nhưng chỉ khuyến nghị cho những người đã từng nhiễm dengue trước đó. Vui lòng tham khảo bác sĩ để đánh giá phù hợp.",
            "omicron": "Không có vaccine riêng cho biến thể Omicron, nhưng các vaccine COVID-19 hiện tại (như Pfizer, Moderna) cung cấp bảo vệ một phần. Bạn nên tiêm nhắc lại theo khuyến cáo của Bộ Y tế.",
            "hiv": "Hiện chưa có vaccine phòng HIV. Các biện pháp phòng ngừa bao gồm sử dụng bao cao su và kiểm tra sức khỏe định kỳ.",
            "sốt xuất huyết": "Vaccine phòng sốt xuất huyết (Dengvaxia) có sẵn ở một số quốc gia, nhưng chỉ khuyến nghị cho những người đã từng nhiễm dengue trước đó. Vui lòng tham khảo bác sĩ để đánh giá phù hợp.",
            "ebola": "Vaccine phòng Ebola (rVSV-ZEBOV) được sử dụng trong các đợt bùng phát, nhưng không phổ biến tại Việt Nam. Liên hệ cơ quan y tế để biết thêm chi tiết.",
            "viêm phổi do virus": "Không có vaccine cụ thể cho viêm phổi do virus nói chung, nhưng vaccine cúm (Vaxigrip Tetra) và phế cầu (Prevenar 13) có thể phòng một số nguyên nhân gây viêm phổi.",
            "sars-cov-2": "Các vaccine COVID-19 (như Pfizer, Moderna, AstraZeneca) được sử dụng rộng rãi. Bạn nên tiêm nhắc lại theo khuyến cáo của Bộ Y tế.",
            "lyme": "Hiện không có vaccine phòng bệnh Lyme cho con người. Biện pháp phòng ngừa bao gồm tránh bị bọ chét cắn khi ở khu vực có nguy cơ.",
            "sốt rét": "Hiện chưa có vaccine phòng sốt rét được sử dụng rộng rãi tại Việt Nam. Vaccine RTS,S/AS01 được thử nghiệm ở một số khu vực, nhưng cần tham khảo bác sĩ.",
            "lao": "Vaccine BCG được sử dụng để phòng lao, đặc biệt cho trẻ sơ sinh. Tuy nhiên, hiệu quả bảo vệ ở người lớn có thể hạn chế.",
            "viêm màng não": "Vaccine phòng viêm màng não (như Menactra, Menveo) có sẵn cho một số chủng vi khuẩn. Tham khảo bác sĩ để chọn loại phù hợp."
        }

        response = disease_vaccine_info.get(disease,
                                            f"Không có thông tin về vaccine cho {disease}. Bạn có thể hỏi về các bệnh khác hoặc tham khảo ý kiến bác sĩ.")
        dispatcher.utter_message(
            text=response,
            buttons=[
                {"title": "Hỏi vaccine khác", "payload": "/ask_vaccine_info"},
                {"title": "Lịch tiêm", "payload": "/ask_vaccination_schedule_by_age"}
            ]
        )
        return [SlotSet("disease", disease)]

class ActionGetVaccineForCondition(Action):
    def name(self) -> Text:
        return "action_get_vaccine_for_condition"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        condition = tracker.get_slot("condition")
        if not condition:
            dispatcher.utter_message(
                text="Xin lỗi, tôi không nhận diện được tình trạng bạn đang hỏi. Vui lòng cung cấp tình trạng cụ thể, ví dụ: dị ứng penicillin."
            )
            return []

        condition = normalize_input(condition)
        condition_vaccine_info = {
            "dị ứng penicillin": "Hầu hết vaccine (như Infanrix Hexa, Hexaxim) không chứa penicillin, nhưng bạn nên kiểm tra với bác sĩ để đảm bảo an toàn, đặc biệt với các vaccine có thành phần phức tạp.",
            "suy giảm miễn dịch": "Người suy giảm miễn dịch (ví dụ: HIV, ung thư) có thể cần tránh một số vaccine sống (như MMR II, Varivax). Vaccine bất hoạt (như Vaxigrip Tetra) thường an toàn hơn, nhưng cần tư vấn bác sĩ.",
            "phụ nữ mang thai": "Một số vaccine như cúm (Vaxigrip Tetra) và bạch hầu-ho gà-uốn ván (Boostrix) được khuyến nghị cho phụ nữ mang thai. Tuy nhiên, vaccine sống (như MMR II) nên tránh. Vui lòng tham khảo bác sĩ.",
            "dị ứng thuốc": "Nếu bạn dị ứng với thuốc, hãy cung cấp thông tin chi tiết cho bác sĩ trước khi tiêm vaccine để kiểm tra thành phần (ví dụ: kháng sinh, chất bảo quản).",
            "trẻ dị ứng sữa": "Hầu hết vaccine không chứa thành phần từ sữa, nhưng bạn nên xác nhận với bác sĩ, đặc biệt với các vaccine như Rotateq hoặc Rotarix.",
            "bệnh tiểu đường": "Người bệnh tiểu đường có thể tiêm hầu hết vaccine (như Vaxigrip Tetra, Pneumovax 23) nếu sức khỏe ổn định. Tham khảo bác sĩ để đảm bảo an toàn.",
            "trẻ tự kỷ": "Trẻ tự kỷ có thể tiêm vaccine theo lịch tiêm chủng thông thường. Không có bằng chứng vaccine gây tự kỷ. Tham khảo bác sĩ nếu có lo ngại.",
            "dị ứng hải sản": "Hầu hết vaccine không chứa thành phần từ hải sản, nhưng bạn nên kiểm tra với bác sĩ để đảm bảo an toàn.",
            "cao huyết áp": "Người cao huyết áp có thể tiêm vaccine nếu huyết áp ổn định. Vaccine như Vaxigrip Tetra hoặc Pneumovax 23 thường an toàn, nhưng nên tham khảo bác sĩ.",
            "trẻ sinh non": "Trẻ sinh non có thể tiêm vaccine theo lịch tiêm chủng, nhưng cần điều chỉnh thời gian dựa trên tuổi điều chỉnh. Tham khảo bác sĩ để có lịch tiêm phù hợp.",
            "bệnh tim": "Người bệnh tim có thể tiêm vaccine nếu tình trạng ổn định. Vaccine như Vaxigrip Tetra hoặc Pneumovax 23 thường được khuyến nghị, nhưng cần tư vấn bác sĩ.",
            "dị ứng latex": "Một số vaccine có thể chứa latex trong nắp lọ hoặc bơm tiêm. Bạn nên kiểm tra với bác sĩ để chọn vaccine an toàn.",
            "bệnh gan": "Người bệnh gan có thể tiêm vaccine nếu tình trạng ổn định. Vaccine viêm gan A (Havax) và viêm gan B (Gene Hbvax A) thường được khuyến nghị, nhưng cần tham khảo bác sĩ.",
            "hen suyễn": "Trẻ bị hen suyễn có thể tiêm vaccine nếu tình trạng được kiểm soát. Vaccine cúm (Vaxigrip Tetra) đặc biệt quan trọng, nhưng cần tham khảo bác sĩ.",
            "dị ứng trứng": "Một số vaccine cúm (như Vaxigrip Tetra) có thể chứa lượng nhỏ protein trứng, nhưng thường an toàn. Tham khảo bác sĩ nếu có tiền sử dị ứng nghiêm trọng.",
            "lupus": "Người bị lupus nên tránh vaccine sống (như MMR II). Vaccine bất hoạt (như Vaxigrip Tetra) thường an toàn, nhưng cần tư vấn bác sĩ."
        }

        response = condition_vaccine_info.get(condition,
                                              f"Đối với {condition}, bạn nên tham khảo ý kiến bác sĩ để chọn vaccine phù hợp. Tôi có thể giúp bạn với thông tin vaccine khác!")
        dispatcher.utter_message(
            text=response,
            buttons=[
                {"title": "Hỏi vaccine khác", "payload": "/ask_vaccine_info"},
                {"title": "Tác dụng phụ", "payload": "/ask_side_effects"}
            ]
        )
        return [SlotSet("condition", condition)]

class ActionAnalyzeOutOfScope(Action):
    def name(self) -> Text:
        return "action_analyze_out_of_scope"

    def run(
            self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        user_input = tracker.latest_message.get("text", "")
        intent = tracker.latest_message.get("intent", {}).get("name", "unknown")
        logger.info(f"Analyzing out-of-scope query: {user_input} (intent: {intent})")
        return []

class ActionAnnotateQuery(Action):
    def name(self) -> Text:
        return "action_annotate_query"

    def run(
            self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        user_input = tracker.latest_message.get("text", "")
        logger.info(f"Annotating query: {user_input}")
        return []

class ActionResetAllSlots(Action):
    def name(self) -> Text:
        return "action_reset_all_slots"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        logger.debug("Resetting all slots")
        return [AllSlotsReset()]