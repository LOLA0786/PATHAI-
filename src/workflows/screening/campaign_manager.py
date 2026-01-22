"""Screening Campaign Manager - TB & Cancer Mass Screening

Self-Explanatory: Workflows for national screening campaigns (TB, cervical cancer, oral cancer).
Why: India runs massive screening programs - 70M+ TB tests, 30M+ cancer screenings annually.
How: Batch processing, AI triage, priority queue, SMS notifications, NIKSHAY integration.

National Programs:
- National TB Elimination Program (NTEP): 70M+ tests/year
- National Cancer Screening Program: Cervical, oral, breast cancer
- Ayushman Bharat screening camps: Rural health missions

Workflow:
1. Campaign created (location, date, disease type)
2. Batch slide upload from camp (10,000+ slides)
3. AI triage: normal → auto-report, suspicious → pathologist queue
4. Priority routing: suspected TB → urgent, normal → routine
5. SMS notifications to patients (in local language)
6. Integration with NIKSHAY (TB) or NCDIR (cancer) APIs
7. Aggregate reports for public health officials

Optimization:
- Pre-processing during upload (quality check, stain normalization)
- Batch AI inference (GPU efficient)
- Parallel processing (10,000 slides/hour target)
"""

import asyncio
import csv
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional
from uuid import uuid4

import structlog
from pydantic import BaseModel
from sqlalchemy import create_engine, text

logger = structlog.get_logger()

# Database
DB_URL = "postgresql://admin:securepass@pathai-db:5432/pathai"
engine = create_engine(DB_URL)


class CampaignType(str, Enum):
    """Screening campaign types"""
    TB = "tb"
    CERVICAL_CANCER = "cervical_cancer"
    ORAL_CANCER = "oral_cancer"
    BREAST_CANCER = "breast_cancer"
    GENERAL = "general"


class CampaignStatus(str, Enum):
    """Campaign status"""
    PLANNED = "planned"
    ACTIVE = "active"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TriageResult(str, Enum):
    """AI triage result"""
    NORMAL = "normal"
    SUSPICIOUS = "suspicious"
    POSITIVE = "positive"
    INDETERMINATE = "indeterminate"


class ScreeningCampaign(BaseModel):
    """Screening campaign model"""
    campaign_id: str
    name: str
    campaign_type: CampaignType
    state: str
    district: str
    location: str  # PHC, CHC, or camp location
    start_date: datetime
    end_date: datetime
    status: CampaignStatus
    target_population: int
    slides_uploaded: int = 0
    slides_processed: int = 0
    positive_cases: int = 0
    suspicious_cases: int = 0
    normal_cases: int = 0
    coordinator_name: str
    coordinator_phone: str
    created_at: datetime
    metadata: Dict = {}


class ScreeningCase(BaseModel):
    """Individual case in screening campaign"""
    case_id: str
    campaign_id: str
    patient_name: str
    patient_age: int
    patient_gender: str
    patient_mobile: Optional[str]
    patient_abha: Optional[str]
    sample_id: str
    slide_id: Optional[str]
    collection_date: datetime
    triage_result: Optional[TriageResult]
    ai_confidence: Optional[float]
    requires_pathologist: bool = False
    pathologist_id: Optional[str]
    final_diagnosis: Optional[str]
    status: str = "pending"  # pending, processing, reported, notified
    created_at: datetime


class CampaignManager:
    """Manager for screening campaigns"""

    def __init__(self):
        self._init_db()
        logger.info("Campaign manager initialized")

    def _init_db(self):
        """Initialize database tables"""
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS screening_campaigns (
                    campaign_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    campaign_type TEXT NOT NULL,
                    state TEXT NOT NULL,
                    district TEXT NOT NULL,
                    location TEXT NOT NULL,
                    start_date TIMESTAMP NOT NULL,
                    end_date TIMESTAMP NOT NULL,
                    status TEXT NOT NULL,
                    target_population INTEGER,
                    slides_uploaded INTEGER DEFAULT 0,
                    slides_processed INTEGER DEFAULT 0,
                    positive_cases INTEGER DEFAULT 0,
                    suspicious_cases INTEGER DEFAULT 0,
                    normal_cases INTEGER DEFAULT 0,
                    coordinator_name TEXT,
                    coordinator_phone TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata JSONB
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS screening_cases (
                    case_id TEXT PRIMARY KEY,
                    campaign_id TEXT REFERENCES screening_campaigns(campaign_id),
                    patient_name TEXT NOT NULL,
                    patient_age INTEGER,
                    patient_gender TEXT,
                    patient_mobile TEXT,
                    patient_abha TEXT,
                    sample_id TEXT NOT NULL,
                    slide_id TEXT,
                    collection_date TIMESTAMP,
                    triage_result TEXT,
                    ai_confidence REAL,
                    requires_pathologist BOOLEAN DEFAULT FALSE,
                    pathologist_id TEXT,
                    final_diagnosis TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_campaign_status
                ON screening_campaigns(status, campaign_type)
            """))

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_case_campaign
                ON screening_cases(campaign_id, status)
            """))

            conn.commit()
            logger.info("Screening database initialized")

    def create_campaign(self, campaign: ScreeningCampaign) -> str:
        """Create new screening campaign

        Args:
            campaign: Campaign details

        Returns:
            campaign_id
        """
        import json

        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO screening_campaigns
                (campaign_id, name, campaign_type, state, district, location,
                 start_date, end_date, status, target_population,
                 coordinator_name, coordinator_phone, created_at, metadata)
                VALUES (:id, :name, :type, :state, :district, :location,
                        :start, :end, :status, :target,
                        :coord_name, :coord_phone, :created, :metadata)
            """), {
                "id": campaign.campaign_id,
                "name": campaign.name,
                "type": campaign.campaign_type.value,
                "state": campaign.state,
                "district": campaign.district,
                "location": campaign.location,
                "start": campaign.start_date,
                "end": campaign.end_date,
                "status": campaign.status.value,
                "target": campaign.target_population,
                "coord_name": campaign.coordinator_name,
                "coord_phone": campaign.coordinator_phone,
                "created": campaign.created_at,
                "metadata": json.dumps(campaign.metadata)
            })
            conn.commit()

        logger.info(
            "Campaign created",
            campaign_id=campaign.campaign_id,
            type=campaign.campaign_type,
            location=f"{campaign.district}, {campaign.state}"
        )

        # Record metric
        from src.utils.metrics import cancer_screening_slides_total, tb_screening_slides_total
        if campaign.campaign_type == CampaignType.TB:
            tb_screening_slides_total.labels(
                state=campaign.state,
                result="pending"
            ).inc(0)  # Initialize counter

        return campaign.campaign_id

    async def batch_register_cases(
        self,
        campaign_id: str,
        cases_csv_path: str
    ) -> int:
        """Batch register cases from CSV

        Args:
            campaign_id: Campaign ID
            cases_csv_path: Path to CSV with patient data

        Returns:
            Number of cases registered
        """
        count = 0

        with open(cases_csv_path, 'r') as f:
            reader = csv.DictReader(f)

            for row in reader:
                case = ScreeningCase(
                    case_id=str(uuid4()),
                    campaign_id=campaign_id,
                    patient_name=row["name"],
                    patient_age=int(row["age"]),
                    patient_gender=row["gender"],
                    patient_mobile=row.get("mobile"),
                    patient_abha=row.get("abha"),
                    sample_id=row["sample_id"],
                    collection_date=datetime.fromisoformat(row["collection_date"]),
                    created_at=datetime.utcnow()
                )

                self._save_case(case)
                count += 1

        logger.info(
            "Batch cases registered",
            campaign_id=campaign_id,
            count=count
        )

        return count

    def _save_case(self, case: ScreeningCase):
        """Save case to database"""
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO screening_cases
                (case_id, campaign_id, patient_name, patient_age, patient_gender,
                 patient_mobile, patient_abha, sample_id, collection_date,
                 created_at, status)
                VALUES (:id, :campaign, :name, :age, :gender,
                        :mobile, :abha, :sample, :collection,
                        :created, :status)
            """), {
                "id": case.case_id,
                "campaign": case.campaign_id,
                "name": case.patient_name,
                "age": case.patient_age,
                "gender": case.patient_gender,
                "mobile": case.patient_mobile,
                "abha": case.patient_abha,
                "sample": case.sample_id,
                "collection": case.collection_date,
                "created": case.created_at,
                "status": case.status
            })
            conn.commit()

    async def process_slide_with_triage(
        self,
        case_id: str,
        slide_id: str,
        campaign_type: CampaignType
    ) -> TriageResult:
        """Process slide with AI triage

        Args:
            case_id: Case ID
            slide_id: Slide ID
            campaign_type: Type of screening

        Returns:
            Triage result
        """
        # Link slide to case
        with engine.connect() as conn:
            conn.execute(text("""
                UPDATE screening_cases
                SET slide_id = :slide, status = 'processing'
                WHERE case_id = :case
            """), {"slide": slide_id, "case": case_id})
            conn.commit()

        # Run AI triage based on campaign type
        if campaign_type == CampaignType.TB:
            triage_result, confidence = await self._triage_tb(slide_id)
        elif campaign_type == CampaignType.CERVICAL_CANCER:
            triage_result, confidence = await self._triage_cervical(slide_id)
        elif campaign_type == CampaignType.ORAL_CANCER:
            triage_result, confidence = await self._triage_oral(slide_id)
        else:
            triage_result, confidence = TriageResult.INDETERMINATE, 0.5

        # Update case with triage result
        requires_pathologist = (
            triage_result in [TriageResult.SUSPICIOUS, TriageResult.POSITIVE] or
            confidence < 0.9
        )

        with engine.connect() as conn:
            conn.execute(text("""
                UPDATE screening_cases
                SET triage_result = :result,
                    ai_confidence = :confidence,
                    requires_pathologist = :requires,
                    status = :status
                WHERE case_id = :case
            """), {
                "result": triage_result.value,
                "confidence": confidence,
                "requires": requires_pathologist,
                "status": "reported" if not requires_pathologist else "pending_review",
                "case": case_id
            })
            conn.commit()

        # Update campaign stats
        self._update_campaign_stats(case_id, triage_result)

        logger.info(
            "Slide triaged",
            case_id=case_id,
            slide_id=slide_id,
            result=triage_result,
            confidence=confidence,
            requires_pathologist=requires_pathologist
        )

        # Record metrics
        from src.utils.metrics import tb_screening_slides_total, cancer_screening_slides_total
        # Get campaign details
        campaign = self._get_campaign_by_case(case_id)
        if campaign:
            if campaign_type == CampaignType.TB:
                tb_screening_slides_total.labels(
                    state=campaign["state"],
                    result=triage_result.value
                ).inc()
            else:
                cancer_screening_slides_total.labels(
                    cancer_type=campaign_type.value,
                    state=campaign["state"],
                    result=triage_result.value
                ).inc()

        return triage_result

    async def _triage_tb(self, slide_id: str) -> tuple[TriageResult, float]:
        """TB-specific AI triage

        Returns:
            (TriageResult, confidence)
        """
        # In production, call TB detection model
        # For now, mock result
        import random

        await asyncio.sleep(0.1)  # Simulate inference

        rand = random.random()
        if rand > 0.95:
            return TriageResult.POSITIVE, 0.92
        elif rand > 0.85:
            return TriageResult.SUSPICIOUS, 0.78
        else:
            return TriageResult.NORMAL, 0.96

    async def _triage_cervical(self, slide_id: str) -> tuple[TriageResult, float]:
        """Cervical cancer triage"""
        import random

        await asyncio.sleep(0.1)

        rand = random.random()
        if rand > 0.93:
            return TriageResult.POSITIVE, 0.89
        elif rand > 0.80:
            return TriageResult.SUSPICIOUS, 0.75
        else:
            return TriageResult.NORMAL, 0.94

    async def _triage_oral(self, slide_id: str) -> tuple[TriageResult, float]:
        """Oral cancer triage"""
        import random

        await asyncio.sleep(0.1)

        rand = random.random()
        if rand > 0.92:
            return TriageResult.POSITIVE, 0.91
        elif rand > 0.78:
            return TriageResult.SUSPICIOUS, 0.77
        else:
            return TriageResult.NORMAL, 0.95

    def _get_campaign_by_case(self, case_id: str) -> Optional[Dict]:
        """Get campaign details from case ID"""
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT c.* FROM screening_campaigns c
                JOIN screening_cases sc ON sc.campaign_id = c.campaign_id
                WHERE sc.case_id = :case
            """), {"case": case_id})

            row = result.fetchone()
            if row:
                return dict(row._mapping)
            return None

    def _update_campaign_stats(self, case_id: str, triage_result: TriageResult):
        """Update campaign statistics"""
        field_map = {
            TriageResult.NORMAL: "normal_cases",
            TriageResult.SUSPICIOUS: "suspicious_cases",
            TriageResult.POSITIVE: "positive_cases"
        }

        field = field_map.get(triage_result)
        if not field:
            return

        with engine.connect() as conn:
            conn.execute(text(f"""
                UPDATE screening_campaigns
                SET {field} = {field} + 1,
                    slides_processed = slides_processed + 1
                WHERE campaign_id = (
                    SELECT campaign_id FROM screening_cases WHERE case_id = :case
                )
            """), {"case": case_id})
            conn.commit()

    async def send_sms_notification(
        self,
        case_id: str,
        message: str,
        language: str = "en"
    ) -> bool:
        """Send SMS notification to patient

        Args:
            case_id: Case ID
            message: Message to send
            language: Language code

        Returns:
            True if sent successfully
        """
        # Get case details
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT patient_mobile, patient_name FROM screening_cases
                WHERE case_id = :case
            """), {"case": case_id})

            row = result.fetchone()
            if not row or not row.patient_mobile:
                logger.warning("No mobile number for SMS", case_id=case_id)
                return False

            mobile = row.patient_mobile
            name = row.patient_name

        # Translate message if needed
        if language != "en":
            from src.localization.translator import translator, Language
            message = await translator.translate_text(
                message, Language(language)
            )

        # Send SMS (integrate with SMS gateway in production)
        logger.info(
            "SMS sent (mock)",
            case_id=case_id,
            mobile=mobile[-4:],  # Last 4 digits only
            language=language
        )

        # In production, integrate with:
        # - Twilio
        # - AWS SNS
        # - Indian SMS gateways (MSG91, Exotel, etc.)

        return True

    def get_campaign_summary(self, campaign_id: str) -> Dict:
        """Get campaign summary with statistics

        Returns:
            Campaign summary dict
        """
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT * FROM screening_campaigns
                WHERE campaign_id = :id
            """), {"id": campaign_id})

            row = result.fetchone()
            if not row:
                return {}

            summary = dict(row._mapping)

            # Calculate additional stats
            if summary["slides_processed"] > 0:
                summary["positive_rate"] = (
                    summary["positive_cases"] / summary["slides_processed"]
                ) * 100
                summary["completion_rate"] = (
                    summary["slides_processed"] / max(summary["target_population"], 1)
                ) * 100

            return summary


# Global instance
campaign_manager = CampaignManager()
