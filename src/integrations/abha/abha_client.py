"""ABHA (Ayushman Bharat Health Account) Integration Client

Self-Explanatory: Integration with India's Ayushman Bharat Digital Mission (ABDM).
Why: Government mandate - all digital health records must link to ABHA.
How: REST API integration with ABDM gateway for ABHA validation, consent management.

ABHA Features:
- ABHA Number (14-digit): Unique health ID for every Indian
- ABHA Address (username@abdm): Human-readable health address
- PHR (Personal Health Record): Patient-controlled health data
- Consent Manager: DPDP-compliant consent for data sharing
- UHI (Unified Health Interface): Interoperability across health apps

Compliance:
- DPDP Act 2023: Patient owns data, explicit consent required
- ABDM Sandbox: Test environment for certification
- Production: ABDM Gateway (gateway.abdm.gov.in)

Flow:
1. Patient provides ABHA number at registration
2. PATHAI validates ABHA via ABDM API
3. Fetch patient demographics from PHR
4. Link pathology reports to ABHA PHR
5. Request consent before sharing with other hospitals
6. Log all ABHA operations for audit

References:
- ABDM Developer Docs: https://abdm.gov.in/abdm
- Sandbox: https://sandbox.abdm.gov.in/
"""

import base64
import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from uuid import uuid4

import httpx
import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()

# Configuration
ABDM_BASE_URL = os.getenv(
    "ABDM_BASE_URL",
    "https://sandbox.abdm.gov.in"  # Sandbox for development
)
ABDM_CLIENT_ID = os.getenv("ABDM_CLIENT_ID", "")
ABDM_CLIENT_SECRET = os.getenv("ABDM_CLIENT_SECRET", "")
HIP_ID = os.getenv("HIP_ID", "PATHAI_HIP_001")  # Health Information Provider ID


class ABHANumber(BaseModel):
    """ABHA Number model"""
    abha_number: str = Field(..., pattern=r"^\d{14}$")  # 14-digit number (Pydantic v2)
    abha_address: Optional[str] = None  # username@abdm
    name: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[str] = None
    mobile: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None


class ConsentRequest(BaseModel):
    """ABDM Consent Request model"""
    consent_id: str
    patient_abha: str
    hip_id: str  # Health Information Provider (us)
    hiu_id: str  # Health Information User (requester)
    purpose: str  # Care management, Research, etc.
    data_from: datetime
    data_to: datetime
    expiry: datetime
    status: str = "REQUESTED"  # REQUESTED, GRANTED, DENIED, EXPIRED


class ABHAClient:
    """Client for ABDM Gateway integration"""

    def __init__(self):
        self.base_url = ABDM_BASE_URL
        self.client_id = ABDM_CLIENT_ID
        self.client_secret = ABDM_CLIENT_SECRET
        self.hip_id = HIP_ID
        self.access_token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None
        logger.info(
            "ABHA Client initialized",
            base_url=self.base_url,
            hip_id=self.hip_id
        )

    async def _get_access_token(self) -> str:
        """Get OAuth2 access token from ABDM Gateway

        Returns:
            Access token for API calls
        """
        # Check if token is still valid
        if self.access_token and self.token_expiry and datetime.utcnow() < self.token_expiry:
            return self.access_token

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.base_url}/v0.5/sessions",
                    json={
                        "clientId": self.client_id,
                        "clientSecret": self.client_secret
                    }
                )
                response.raise_for_status()
                data = response.json()

                self.access_token = data["accessToken"]
                # Token valid for 30 minutes typically
                self.token_expiry = datetime.utcnow() + timedelta(minutes=25)

                logger.info("ABDM access token obtained")
                return self.access_token

        except httpx.HTTPError as e:
            logger.error("Failed to get ABDM access token", error=str(e))
            raise

    async def validate_abha_number(self, abha_number: str) -> Optional[ABHANumber]:
        """Validate ABHA number and fetch patient details

        Args:
            abha_number: 14-digit ABHA number

        Returns:
            ABHANumber object with patient details, or None if invalid
        """
        try:
            token = await self._get_access_token()

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self.base_url}/v1/search/searchByHealthId",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "X-CM-ID": "sbx"  # Sandbox identifier
                    },
                    params={"healthId": abha_number}
                )

                if response.status_code == 200:
                    data = response.json()

                    abha = ABHANumber(
                        abha_number=data.get("healthIdNumber", abha_number),
                        abha_address=data.get("healthId"),
                        name=data.get("name"),
                        gender=data.get("gender"),
                        date_of_birth=data.get("dayOfBirth"),
                        mobile=data.get("mobile"),
                        state=data.get("stateName"),
                        district=data.get("districtName")
                    )

                    logger.info(
                        "ABHA number validated",
                        abha_number=abha_number,
                        name=abha.name
                    )

                    # Record metric
                    from src.utils.metrics import abha_validations_total
                    abha_validations_total.labels(result="valid").inc()

                    return abha

                elif response.status_code == 404:
                    logger.warning("ABHA number not found", abha_number=abha_number)

                    from src.utils.metrics import abha_validations_total
                    abha_validations_total.labels(result="invalid").inc()

                    return None
                else:
                    logger.error(
                        "ABHA validation error",
                        status=response.status_code,
                        response=response.text
                    )

                    from src.utils.metrics import abha_validations_total
                    abha_validations_total.labels(result="api_error").inc()

                    return None

        except Exception as e:
            logger.error("ABHA validation exception", error=str(e))

            from src.utils.metrics import abha_validations_total
            abha_validations_total.labels(result="api_error").inc()

            return None

    async def create_abha_address(
        self,
        preferred_address: str,
        mobile: str,
        otp: str
    ) -> Optional[str]:
        """Create ABHA address (username@abdm) for patient

        Args:
            preferred_address: Desired username (check availability first)
            mobile: Mobile number for OTP verification
            otp: OTP sent to mobile

        Returns:
            Created ABHA address, or None if failed
        """
        try:
            token = await self._get_access_token()

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.base_url}/v1/registration/aadhaar/createHealthIdWithPreVerified",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "X-CM-ID": "sbx"
                    },
                    json={
                        "healthId": preferred_address,
                        "mobile": mobile,
                        "txnId": otp  # Transaction ID from OTP flow
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    abha_address = data.get("healthId")

                    logger.info(
                        "ABHA address created",
                        address=abha_address,
                        mobile=mobile
                    )

                    return abha_address
                else:
                    logger.error(
                        "ABHA address creation failed",
                        status=response.status_code,
                        response=response.text
                    )
                    return None

        except Exception as e:
            logger.error("ABHA address creation exception", error=str(e))
            return None

    async def link_report_to_phr(
        self,
        abha_number: str,
        report_id: str,
        report_type: str,
        report_data: Dict
    ) -> bool:
        """Link pathology report to patient's PHR

        Args:
            abha_number: Patient's ABHA number
            report_id: Unique report ID
            report_type: Type of report (histopathology, cytology, etc.)
            report_data: Report data to store

        Returns:
            True if successful
        """
        try:
            token = await self._get_access_token()

            # Create FHIR DiagnosticReport resource
            fhir_report = self._create_fhir_diagnostic_report(
                report_id, report_type, report_data
            )

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.base_url}/v0.5/health-information/hip/on-request",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "X-CM-ID": "sbx",
                        "X-HIP-ID": self.hip_id
                    },
                    json={
                        "healthId": abha_number,
                        "careContexts": [
                            {
                                "referenceNumber": report_id,
                                "display": f"Pathology Report - {report_type}"
                            }
                        ],
                        "hiTypes": ["DiagnosticReport"],
                        "entries": [fhir_report]
                    }
                )

                if response.status_code == 202:  # Accepted
                    logger.info(
                        "Report linked to PHR",
                        abha_number=abha_number,
                        report_id=report_id
                    )
                    return True
                else:
                    logger.error(
                        "PHR linking failed",
                        status=response.status_code,
                        response=response.text
                    )
                    return False

        except Exception as e:
            logger.error("PHR linking exception", error=str(e))
            return False

    async def request_consent(
        self,
        patient_abha: str,
        requester_hip_id: str,
        purpose: str,
        data_from: datetime,
        data_to: datetime,
        expiry_hours: int = 24
    ) -> Optional[str]:
        """Request consent from patient to share health data

        Args:
            patient_abha: Patient's ABHA number
            requester_hip_id: Health Information Provider requesting data
            purpose: Purpose of data access
            data_from: Start date for data access
            data_to: End date for data access
            expiry_hours: Consent validity in hours

        Returns:
            Consent request ID for tracking
        """
        try:
            token = await self._get_access_token()
            consent_id = str(uuid4())

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.base_url}/v0.5/consent-requests/init",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "X-CM-ID": "sbx"
                    },
                    json={
                        "requestId": str(uuid4()),
                        "timestamp": datetime.utcnow().isoformat(),
                        "consent": {
                            "purpose": {
                                "code": purpose,
                                "text": self._get_purpose_text(purpose)
                            },
                            "patient": {"id": patient_abha},
                            "hip": {"id": self.hip_id},
                            "hiu": {"id": requester_hip_id},
                            "requester": {
                                "name": "PATHAI",
                                "identifier": {
                                    "type": "HIP",
                                    "value": self.hip_id
                                }
                            },
                            "hiTypes": ["DiagnosticReport"],
                            "permission": {
                                "accessMode": "VIEW",
                                "dateRange": {
                                    "from": data_from.isoformat(),
                                    "to": data_to.isoformat()
                                },
                                "dataEraseAt": (
                                    datetime.utcnow() + timedelta(hours=expiry_hours)
                                ).isoformat()
                            }
                        }
                    }
                )

                if response.status_code == 202:
                    data = response.json()
                    consent_request_id = data.get("id", consent_id)

                    logger.info(
                        "Consent requested",
                        patient_abha=patient_abha,
                        consent_id=consent_request_id,
                        purpose=purpose
                    )

                    return consent_request_id
                else:
                    logger.error(
                        "Consent request failed",
                        status=response.status_code,
                        response=response.text
                    )
                    return None

        except Exception as e:
            logger.error("Consent request exception", error=str(e))
            return None

    async def check_consent_status(self, consent_id: str) -> Optional[str]:
        """Check status of consent request

        Args:
            consent_id: Consent request ID

        Returns:
            Status: REQUESTED, GRANTED, DENIED, EXPIRED
        """
        try:
            token = await self._get_access_token()

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self.base_url}/v0.5/consent-requests/{consent_id}",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "X-CM-ID": "sbx"
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status", "UNKNOWN")

                    logger.info(
                        "Consent status checked",
                        consent_id=consent_id,
                        status=status
                    )

                    # Record metric
                    from src.utils.metrics import consent_checks_total
                    consent_checks_total.labels(result=status.lower()).inc()

                    return status
                else:
                    logger.error(
                        "Consent status check failed",
                        status=response.status_code
                    )
                    return None

        except Exception as e:
            logger.error("Consent status check exception", error=str(e))
            return None

    def _create_fhir_diagnostic_report(
        self,
        report_id: str,
        report_type: str,
        report_data: Dict
    ) -> Dict:
        """Create FHIR DiagnosticReport resource

        Args:
            report_id: Unique report ID
            report_type: Type of report
            report_data: Report data

        Returns:
            FHIR-compliant DiagnosticReport resource
        """
        return {
            "resourceType": "DiagnosticReport",
            "id": report_id,
            "status": "final",
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v2-0074",
                            "code": "PAT",
                            "display": "Pathology"
                        }
                    ]
                }
            ],
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "60567-5",
                        "display": "Comprehensive pathology report"
                    }
                ],
                "text": report_type
            },
            "issued": datetime.utcnow().isoformat(),
            "conclusion": report_data.get("conclusion", ""),
            "presentedForm": [
                {
                    "contentType": "application/pdf",
                    "data": report_data.get("pdf_base64", ""),
                    "title": f"Pathology Report - {report_type}"
                }
            ]
        }

    def _get_purpose_text(self, purpose_code: str) -> str:
        """Get human-readable purpose text

        Args:
            purpose_code: Purpose code

        Returns:
            Human-readable text
        """
        purposes = {
            "CAREMGT": "Care Management",
            "BTG": "Break the Glass (Emergency)",
            "PUBHLTH": "Public Health",
            "HPAYMT": "Healthcare Payment",
            "DSRCH": "Disease Specific Healthcare Research"
        }
        return purposes.get(purpose_code, "Healthcare Service")


# Global instance
abha_client = ABHAClient()
