"""ABHA Router - API endpoints for Ayushman Bharat integration

Endpoints:
- POST /abha/validate: Validate ABHA number
- POST /abha/link-report: Link pathology report to PHR
- POST /abha/request-consent: Request consent for data sharing
- GET /abha/consent-status/{consent_id}: Check consent status
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Optional
from datetime import datetime
from pydantic import BaseModel
import structlog

from src.governance.auth import check_role
from src.integrations.abha.abha_client import abha_client

router = APIRouter()
logger = structlog.get_logger()


class ValidateABHARequest(BaseModel):
    abha_number: str


class LinkReportRequest(BaseModel):
    abha_number: str
    report_id: str
    report_type: str
    report_data: Dict


class ConsentRequestModel(BaseModel):
    patient_abha: str
    requester_hip_id: str
    purpose: str
    data_from: datetime
    data_to: datetime
    expiry_hours: int = 24


@router.post("/validate")
async def validate_abha(
    request: ValidateABHARequest,
    user: Dict = Depends(check_role("metadata"))
):
    """Validate ABHA number and fetch patient details

    Args:
        request: ABHA validation request

    Returns:
        Patient demographics if valid, error if invalid
    """
    try:
        abha_data = await abha_client.validate_abha_number(request.abha_number)

        if abha_data:
            logger.info(
                "ABHA validated via API",
                abha_number=request.abha_number,
                user_id=user["user_id"]
            )

            return {
                "valid": True,
                "abha_number": abha_data.abha_number,
                "abha_address": abha_data.abha_address,
                "name": abha_data.name,
                "gender": abha_data.gender,
                "date_of_birth": abha_data.date_of_birth,
                "state": abha_data.state,
                "district": abha_data.district
            }
        else:
            raise HTTPException(
                status_code=404,
                detail="ABHA number not found or invalid"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("ABHA validation error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/link-report")
async def link_report(
    request: LinkReportRequest,
    user: Dict = Depends(check_role("upload"))
):
    """Link pathology report to patient's ABHA PHR

    Args:
        request: Report linking request

    Returns:
        Success status
    """
    try:
        success = await abha_client.link_report_to_phr(
            abha_number=request.abha_number,
            report_id=request.report_id,
            report_type=request.report_type,
            report_data=request.report_data
        )

        if success:
            logger.info(
                "Report linked to PHR",
                report_id=request.report_id,
                abha=request.abha_number,
                user_id=user["user_id"]
            )

            return {
                "success": True,
                "message": "Report linked to ABHA PHR",
                "report_id": request.report_id
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to link report to PHR"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Report linking error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/request-consent")
async def request_consent(
    request: ConsentRequestModel,
    user: Dict = Depends(check_role("metadata"))
):
    """Request consent from patient to share health data

    Args:
        request: Consent request details

    Returns:
        Consent request ID for tracking
    """
    try:
        consent_id = await abha_client.request_consent(
            patient_abha=request.patient_abha,
            requester_hip_id=request.requester_hip_id,
            purpose=request.purpose,
            data_from=request.data_from,
            data_to=request.data_to,
            expiry_hours=request.expiry_hours
        )

        if consent_id:
            logger.info(
                "Consent requested",
                consent_id=consent_id,
                patient_abha=request.patient_abha,
                user_id=user["user_id"]
            )

            return {
                "success": True,
                "consent_id": consent_id,
                "message": "Consent request sent to patient",
                "status": "REQUESTED"
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to create consent request"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Consent request error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/consent-status/{consent_id}")
async def get_consent_status(
    consent_id: str,
    user: Dict = Depends(check_role("metadata"))
):
    """Check status of consent request

    Args:
        consent_id: Consent request ID

    Returns:
        Current consent status
    """
    try:
        status = await abha_client.check_consent_status(consent_id)

        if status:
            return {
                "consent_id": consent_id,
                "status": status,
                "granted": status == "GRANTED"
            }
        else:
            raise HTTPException(
                status_code=404,
                detail="Consent request not found"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Consent status check error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def abha_home():
    return {
        "message": "PATHAI ABHA Integration",
        "features": [
            "ABHA number validation",
            "PHR linking for pathology reports",
            "DPDP-compliant consent management",
            "FHIR DiagnosticReport support"
        ],
        "compliance": "ABDM-certified (sandbox mode)"
    }
