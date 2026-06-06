from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="CatalogAttributes")


@_attrs_define
class CatalogAttributes:
    """Catalog application attributes sourced from the Universal Application Directory (UAD)

    Attributes:
        spoof_risk_level (None | str | Unset):
        disaster_recovery (bool | None | Unset):
        encryption_in_transit (bool | None | Unset):
        native_data_classification (bool | None | Unset):
        audit_log (bool | None | Unset):
        data_retention (None | str | Unset):
        file_content_sharing (bool | None | Unset):
        session_timeout (None | str | Unset):
        encryption_at_rest (bool | None | Unset):
        encryption_strength_at_rest (None | str | Unset):
        protected_from_downgrade_attacks (bool | None | Unset):
        privacy_policy (bool | None | Unset):
        data_ownership (None | str | Unset):
        third_party_data_sharing (bool | None | Unset):
        http_security_headers (None | str | Unset):
        terms_and_conditions (bool | None | Unset):
        iso_9000 (bool | None | Unset):
        iso_9001 (bool | None | Unset):
        iso_27001 (bool | None | Unset):
        iso_27002 (bool | None | Unset):
        iso_27017 (bool | None | Unset):
        iso_27018 (bool | None | Unset):
        soc1 (bool | None | Unset):
        soc2 (bool | None | Unset):
        pci (bool | None | Unset):
        hipaa (bool | None | Unset):
        gdpr (bool | None | Unset):
        ferpa (bool | None | Unset):
        coppa (bool | None | Unset):
        finra (bool | None | Unset):
        ffiec (bool | None | Unset):
        glba (bool | None | Unset):
        gapp (bool | None | Unset):
        itar (bool | None | Unset):
        hitrust_csf (bool | None | Unset):
        trustarc (bool | None | Unset):
        fedramp (bool | None | Unset):
        c5 (bool | None | Unset):
        ssae18 (bool | None | Unset):
        nist_sp_80053 (bool | None | Unset):
        fisma (bool | None | Unset):
        privacy_mark_japan (bool | None | Unset):
        privacy_shield (bool | None | Unset):
        safe_harbor (bool | None | Unset):
        cobit (bool | None | Unset):
        csa_star (bool | None | Unset):
        jericho_forum_comm (bool | None | Unset):
        sox (bool | None | Unset):
        cjis (bool | None | Unset):
        isae_3402 (bool | None | Unset):
        input_data_types (list[str] | None | Unset):
        output_data_types (list[str] | None | Unset):
        consumption_modes (list[str] | None | Unset):
        genai_types (list[str] | None | Unset):
        data_used_in_models (None | str | Unset):
        allows_fine_tuning (bool | None | Unset):
        has_marketplace (bool | None | Unset):
        input_monitoring_and_review (None | str | Unset):
        security_guardrails (list[str] | None | Unset):
        copyright_indemnity (None | str | Unset):
        rbac (bool | None | Unset):
        mfa (bool | None | Unset):
        password_policy (bool | None | Unset):
        ip_based_restrictions (bool | None | Unset):
        saml (bool | None | Unset):
        quantum_readiness (bool | None | Unset):
        pqc_method (list[str] | None | Unset):
    """

    spoof_risk_level: None | str | Unset = UNSET
    disaster_recovery: bool | None | Unset = UNSET
    encryption_in_transit: bool | None | Unset = UNSET
    native_data_classification: bool | None | Unset = UNSET
    audit_log: bool | None | Unset = UNSET
    data_retention: None | str | Unset = UNSET
    file_content_sharing: bool | None | Unset = UNSET
    session_timeout: None | str | Unset = UNSET
    encryption_at_rest: bool | None | Unset = UNSET
    encryption_strength_at_rest: None | str | Unset = UNSET
    protected_from_downgrade_attacks: bool | None | Unset = UNSET
    privacy_policy: bool | None | Unset = UNSET
    data_ownership: None | str | Unset = UNSET
    third_party_data_sharing: bool | None | Unset = UNSET
    http_security_headers: None | str | Unset = UNSET
    terms_and_conditions: bool | None | Unset = UNSET
    iso_9000: bool | None | Unset = UNSET
    iso_9001: bool | None | Unset = UNSET
    iso_27001: bool | None | Unset = UNSET
    iso_27002: bool | None | Unset = UNSET
    iso_27017: bool | None | Unset = UNSET
    iso_27018: bool | None | Unset = UNSET
    soc1: bool | None | Unset = UNSET
    soc2: bool | None | Unset = UNSET
    pci: bool | None | Unset = UNSET
    hipaa: bool | None | Unset = UNSET
    gdpr: bool | None | Unset = UNSET
    ferpa: bool | None | Unset = UNSET
    coppa: bool | None | Unset = UNSET
    finra: bool | None | Unset = UNSET
    ffiec: bool | None | Unset = UNSET
    glba: bool | None | Unset = UNSET
    gapp: bool | None | Unset = UNSET
    itar: bool | None | Unset = UNSET
    hitrust_csf: bool | None | Unset = UNSET
    trustarc: bool | None | Unset = UNSET
    fedramp: bool | None | Unset = UNSET
    c5: bool | None | Unset = UNSET
    ssae18: bool | None | Unset = UNSET
    nist_sp_80053: bool | None | Unset = UNSET
    fisma: bool | None | Unset = UNSET
    privacy_mark_japan: bool | None | Unset = UNSET
    privacy_shield: bool | None | Unset = UNSET
    safe_harbor: bool | None | Unset = UNSET
    cobit: bool | None | Unset = UNSET
    csa_star: bool | None | Unset = UNSET
    jericho_forum_comm: bool | None | Unset = UNSET
    sox: bool | None | Unset = UNSET
    cjis: bool | None | Unset = UNSET
    isae_3402: bool | None | Unset = UNSET
    input_data_types: list[str] | None | Unset = UNSET
    output_data_types: list[str] | None | Unset = UNSET
    consumption_modes: list[str] | None | Unset = UNSET
    genai_types: list[str] | None | Unset = UNSET
    data_used_in_models: None | str | Unset = UNSET
    allows_fine_tuning: bool | None | Unset = UNSET
    has_marketplace: bool | None | Unset = UNSET
    input_monitoring_and_review: None | str | Unset = UNSET
    security_guardrails: list[str] | None | Unset = UNSET
    copyright_indemnity: None | str | Unset = UNSET
    rbac: bool | None | Unset = UNSET
    mfa: bool | None | Unset = UNSET
    password_policy: bool | None | Unset = UNSET
    ip_based_restrictions: bool | None | Unset = UNSET
    saml: bool | None | Unset = UNSET
    quantum_readiness: bool | None | Unset = UNSET
    pqc_method: list[str] | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        spoof_risk_level: None | str | Unset
        if isinstance(self.spoof_risk_level, Unset):
            spoof_risk_level = UNSET
        else:
            spoof_risk_level = self.spoof_risk_level

        disaster_recovery: bool | None | Unset
        if isinstance(self.disaster_recovery, Unset):
            disaster_recovery = UNSET
        else:
            disaster_recovery = self.disaster_recovery

        encryption_in_transit: bool | None | Unset
        if isinstance(self.encryption_in_transit, Unset):
            encryption_in_transit = UNSET
        else:
            encryption_in_transit = self.encryption_in_transit

        native_data_classification: bool | None | Unset
        if isinstance(self.native_data_classification, Unset):
            native_data_classification = UNSET
        else:
            native_data_classification = self.native_data_classification

        audit_log: bool | None | Unset
        if isinstance(self.audit_log, Unset):
            audit_log = UNSET
        else:
            audit_log = self.audit_log

        data_retention: None | str | Unset
        if isinstance(self.data_retention, Unset):
            data_retention = UNSET
        else:
            data_retention = self.data_retention

        file_content_sharing: bool | None | Unset
        if isinstance(self.file_content_sharing, Unset):
            file_content_sharing = UNSET
        else:
            file_content_sharing = self.file_content_sharing

        session_timeout: None | str | Unset
        if isinstance(self.session_timeout, Unset):
            session_timeout = UNSET
        else:
            session_timeout = self.session_timeout

        encryption_at_rest: bool | None | Unset
        if isinstance(self.encryption_at_rest, Unset):
            encryption_at_rest = UNSET
        else:
            encryption_at_rest = self.encryption_at_rest

        encryption_strength_at_rest: None | str | Unset
        if isinstance(self.encryption_strength_at_rest, Unset):
            encryption_strength_at_rest = UNSET
        else:
            encryption_strength_at_rest = self.encryption_strength_at_rest

        protected_from_downgrade_attacks: bool | None | Unset
        if isinstance(self.protected_from_downgrade_attacks, Unset):
            protected_from_downgrade_attacks = UNSET
        else:
            protected_from_downgrade_attacks = self.protected_from_downgrade_attacks

        privacy_policy: bool | None | Unset
        if isinstance(self.privacy_policy, Unset):
            privacy_policy = UNSET
        else:
            privacy_policy = self.privacy_policy

        data_ownership: None | str | Unset
        if isinstance(self.data_ownership, Unset):
            data_ownership = UNSET
        else:
            data_ownership = self.data_ownership

        third_party_data_sharing: bool | None | Unset
        if isinstance(self.third_party_data_sharing, Unset):
            third_party_data_sharing = UNSET
        else:
            third_party_data_sharing = self.third_party_data_sharing

        http_security_headers: None | str | Unset
        if isinstance(self.http_security_headers, Unset):
            http_security_headers = UNSET
        else:
            http_security_headers = self.http_security_headers

        terms_and_conditions: bool | None | Unset
        if isinstance(self.terms_and_conditions, Unset):
            terms_and_conditions = UNSET
        else:
            terms_and_conditions = self.terms_and_conditions

        iso_9000: bool | None | Unset
        if isinstance(self.iso_9000, Unset):
            iso_9000 = UNSET
        else:
            iso_9000 = self.iso_9000

        iso_9001: bool | None | Unset
        if isinstance(self.iso_9001, Unset):
            iso_9001 = UNSET
        else:
            iso_9001 = self.iso_9001

        iso_27001: bool | None | Unset
        if isinstance(self.iso_27001, Unset):
            iso_27001 = UNSET
        else:
            iso_27001 = self.iso_27001

        iso_27002: bool | None | Unset
        if isinstance(self.iso_27002, Unset):
            iso_27002 = UNSET
        else:
            iso_27002 = self.iso_27002

        iso_27017: bool | None | Unset
        if isinstance(self.iso_27017, Unset):
            iso_27017 = UNSET
        else:
            iso_27017 = self.iso_27017

        iso_27018: bool | None | Unset
        if isinstance(self.iso_27018, Unset):
            iso_27018 = UNSET
        else:
            iso_27018 = self.iso_27018

        soc1: bool | None | Unset
        if isinstance(self.soc1, Unset):
            soc1 = UNSET
        else:
            soc1 = self.soc1

        soc2: bool | None | Unset
        if isinstance(self.soc2, Unset):
            soc2 = UNSET
        else:
            soc2 = self.soc2

        pci: bool | None | Unset
        if isinstance(self.pci, Unset):
            pci = UNSET
        else:
            pci = self.pci

        hipaa: bool | None | Unset
        if isinstance(self.hipaa, Unset):
            hipaa = UNSET
        else:
            hipaa = self.hipaa

        gdpr: bool | None | Unset
        if isinstance(self.gdpr, Unset):
            gdpr = UNSET
        else:
            gdpr = self.gdpr

        ferpa: bool | None | Unset
        if isinstance(self.ferpa, Unset):
            ferpa = UNSET
        else:
            ferpa = self.ferpa

        coppa: bool | None | Unset
        if isinstance(self.coppa, Unset):
            coppa = UNSET
        else:
            coppa = self.coppa

        finra: bool | None | Unset
        if isinstance(self.finra, Unset):
            finra = UNSET
        else:
            finra = self.finra

        ffiec: bool | None | Unset
        if isinstance(self.ffiec, Unset):
            ffiec = UNSET
        else:
            ffiec = self.ffiec

        glba: bool | None | Unset
        if isinstance(self.glba, Unset):
            glba = UNSET
        else:
            glba = self.glba

        gapp: bool | None | Unset
        if isinstance(self.gapp, Unset):
            gapp = UNSET
        else:
            gapp = self.gapp

        itar: bool | None | Unset
        if isinstance(self.itar, Unset):
            itar = UNSET
        else:
            itar = self.itar

        hitrust_csf: bool | None | Unset
        if isinstance(self.hitrust_csf, Unset):
            hitrust_csf = UNSET
        else:
            hitrust_csf = self.hitrust_csf

        trustarc: bool | None | Unset
        if isinstance(self.trustarc, Unset):
            trustarc = UNSET
        else:
            trustarc = self.trustarc

        fedramp: bool | None | Unset
        if isinstance(self.fedramp, Unset):
            fedramp = UNSET
        else:
            fedramp = self.fedramp

        c5: bool | None | Unset
        if isinstance(self.c5, Unset):
            c5 = UNSET
        else:
            c5 = self.c5

        ssae18: bool | None | Unset
        if isinstance(self.ssae18, Unset):
            ssae18 = UNSET
        else:
            ssae18 = self.ssae18

        nist_sp_80053: bool | None | Unset
        if isinstance(self.nist_sp_80053, Unset):
            nist_sp_80053 = UNSET
        else:
            nist_sp_80053 = self.nist_sp_80053

        fisma: bool | None | Unset
        if isinstance(self.fisma, Unset):
            fisma = UNSET
        else:
            fisma = self.fisma

        privacy_mark_japan: bool | None | Unset
        if isinstance(self.privacy_mark_japan, Unset):
            privacy_mark_japan = UNSET
        else:
            privacy_mark_japan = self.privacy_mark_japan

        privacy_shield: bool | None | Unset
        if isinstance(self.privacy_shield, Unset):
            privacy_shield = UNSET
        else:
            privacy_shield = self.privacy_shield

        safe_harbor: bool | None | Unset
        if isinstance(self.safe_harbor, Unset):
            safe_harbor = UNSET
        else:
            safe_harbor = self.safe_harbor

        cobit: bool | None | Unset
        if isinstance(self.cobit, Unset):
            cobit = UNSET
        else:
            cobit = self.cobit

        csa_star: bool | None | Unset
        if isinstance(self.csa_star, Unset):
            csa_star = UNSET
        else:
            csa_star = self.csa_star

        jericho_forum_comm: bool | None | Unset
        if isinstance(self.jericho_forum_comm, Unset):
            jericho_forum_comm = UNSET
        else:
            jericho_forum_comm = self.jericho_forum_comm

        sox: bool | None | Unset
        if isinstance(self.sox, Unset):
            sox = UNSET
        else:
            sox = self.sox

        cjis: bool | None | Unset
        if isinstance(self.cjis, Unset):
            cjis = UNSET
        else:
            cjis = self.cjis

        isae_3402: bool | None | Unset
        if isinstance(self.isae_3402, Unset):
            isae_3402 = UNSET
        else:
            isae_3402 = self.isae_3402

        input_data_types: list[str] | None | Unset
        if isinstance(self.input_data_types, Unset):
            input_data_types = UNSET
        elif isinstance(self.input_data_types, list):
            input_data_types = self.input_data_types

        else:
            input_data_types = self.input_data_types

        output_data_types: list[str] | None | Unset
        if isinstance(self.output_data_types, Unset):
            output_data_types = UNSET
        elif isinstance(self.output_data_types, list):
            output_data_types = self.output_data_types

        else:
            output_data_types = self.output_data_types

        consumption_modes: list[str] | None | Unset
        if isinstance(self.consumption_modes, Unset):
            consumption_modes = UNSET
        elif isinstance(self.consumption_modes, list):
            consumption_modes = self.consumption_modes

        else:
            consumption_modes = self.consumption_modes

        genai_types: list[str] | None | Unset
        if isinstance(self.genai_types, Unset):
            genai_types = UNSET
        elif isinstance(self.genai_types, list):
            genai_types = self.genai_types

        else:
            genai_types = self.genai_types

        data_used_in_models: None | str | Unset
        if isinstance(self.data_used_in_models, Unset):
            data_used_in_models = UNSET
        else:
            data_used_in_models = self.data_used_in_models

        allows_fine_tuning: bool | None | Unset
        if isinstance(self.allows_fine_tuning, Unset):
            allows_fine_tuning = UNSET
        else:
            allows_fine_tuning = self.allows_fine_tuning

        has_marketplace: bool | None | Unset
        if isinstance(self.has_marketplace, Unset):
            has_marketplace = UNSET
        else:
            has_marketplace = self.has_marketplace

        input_monitoring_and_review: None | str | Unset
        if isinstance(self.input_monitoring_and_review, Unset):
            input_monitoring_and_review = UNSET
        else:
            input_monitoring_and_review = self.input_monitoring_and_review

        security_guardrails: list[str] | None | Unset
        if isinstance(self.security_guardrails, Unset):
            security_guardrails = UNSET
        elif isinstance(self.security_guardrails, list):
            security_guardrails = self.security_guardrails

        else:
            security_guardrails = self.security_guardrails

        copyright_indemnity: None | str | Unset
        if isinstance(self.copyright_indemnity, Unset):
            copyright_indemnity = UNSET
        else:
            copyright_indemnity = self.copyright_indemnity

        rbac: bool | None | Unset
        if isinstance(self.rbac, Unset):
            rbac = UNSET
        else:
            rbac = self.rbac

        mfa: bool | None | Unset
        if isinstance(self.mfa, Unset):
            mfa = UNSET
        else:
            mfa = self.mfa

        password_policy: bool | None | Unset
        if isinstance(self.password_policy, Unset):
            password_policy = UNSET
        else:
            password_policy = self.password_policy

        ip_based_restrictions: bool | None | Unset
        if isinstance(self.ip_based_restrictions, Unset):
            ip_based_restrictions = UNSET
        else:
            ip_based_restrictions = self.ip_based_restrictions

        saml: bool | None | Unset
        if isinstance(self.saml, Unset):
            saml = UNSET
        else:
            saml = self.saml

        quantum_readiness: bool | None | Unset
        if isinstance(self.quantum_readiness, Unset):
            quantum_readiness = UNSET
        else:
            quantum_readiness = self.quantum_readiness

        pqc_method: list[str] | None | Unset
        if isinstance(self.pqc_method, Unset):
            pqc_method = UNSET
        elif isinstance(self.pqc_method, list):
            pqc_method = self.pqc_method

        else:
            pqc_method = self.pqc_method

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if spoof_risk_level is not UNSET:
            field_dict["spoof_risk_level"] = spoof_risk_level
        if disaster_recovery is not UNSET:
            field_dict["disaster_recovery"] = disaster_recovery
        if encryption_in_transit is not UNSET:
            field_dict["encryption_in_transit"] = encryption_in_transit
        if native_data_classification is not UNSET:
            field_dict["native_data_classification"] = native_data_classification
        if audit_log is not UNSET:
            field_dict["audit_log"] = audit_log
        if data_retention is not UNSET:
            field_dict["data_retention"] = data_retention
        if file_content_sharing is not UNSET:
            field_dict["file_content_sharing"] = file_content_sharing
        if session_timeout is not UNSET:
            field_dict["session_timeout"] = session_timeout
        if encryption_at_rest is not UNSET:
            field_dict["encryption_at_rest"] = encryption_at_rest
        if encryption_strength_at_rest is not UNSET:
            field_dict["encryption_strength_at_rest"] = encryption_strength_at_rest
        if protected_from_downgrade_attacks is not UNSET:
            field_dict["protected_from_downgrade_attacks"] = protected_from_downgrade_attacks
        if privacy_policy is not UNSET:
            field_dict["privacy_policy"] = privacy_policy
        if data_ownership is not UNSET:
            field_dict["data_ownership"] = data_ownership
        if third_party_data_sharing is not UNSET:
            field_dict["third_party_data_sharing"] = third_party_data_sharing
        if http_security_headers is not UNSET:
            field_dict["http_security_headers"] = http_security_headers
        if terms_and_conditions is not UNSET:
            field_dict["terms_and_conditions"] = terms_and_conditions
        if iso_9000 is not UNSET:
            field_dict["iso_9000"] = iso_9000
        if iso_9001 is not UNSET:
            field_dict["iso_9001"] = iso_9001
        if iso_27001 is not UNSET:
            field_dict["iso_27001"] = iso_27001
        if iso_27002 is not UNSET:
            field_dict["iso_27002"] = iso_27002
        if iso_27017 is not UNSET:
            field_dict["iso_27017"] = iso_27017
        if iso_27018 is not UNSET:
            field_dict["iso_27018"] = iso_27018
        if soc1 is not UNSET:
            field_dict["soc1"] = soc1
        if soc2 is not UNSET:
            field_dict["soc2"] = soc2
        if pci is not UNSET:
            field_dict["pci"] = pci
        if hipaa is not UNSET:
            field_dict["hipaa"] = hipaa
        if gdpr is not UNSET:
            field_dict["gdpr"] = gdpr
        if ferpa is not UNSET:
            field_dict["ferpa"] = ferpa
        if coppa is not UNSET:
            field_dict["coppa"] = coppa
        if finra is not UNSET:
            field_dict["finra"] = finra
        if ffiec is not UNSET:
            field_dict["ffiec"] = ffiec
        if glba is not UNSET:
            field_dict["glba"] = glba
        if gapp is not UNSET:
            field_dict["gapp"] = gapp
        if itar is not UNSET:
            field_dict["itar"] = itar
        if hitrust_csf is not UNSET:
            field_dict["hitrust_csf"] = hitrust_csf
        if trustarc is not UNSET:
            field_dict["trustarc"] = trustarc
        if fedramp is not UNSET:
            field_dict["fedramp"] = fedramp
        if c5 is not UNSET:
            field_dict["c5"] = c5
        if ssae18 is not UNSET:
            field_dict["ssae18"] = ssae18
        if nist_sp_80053 is not UNSET:
            field_dict["nist_sp_80053"] = nist_sp_80053
        if fisma is not UNSET:
            field_dict["fisma"] = fisma
        if privacy_mark_japan is not UNSET:
            field_dict["privacy_mark_japan"] = privacy_mark_japan
        if privacy_shield is not UNSET:
            field_dict["privacy_shield"] = privacy_shield
        if safe_harbor is not UNSET:
            field_dict["safe_harbor"] = safe_harbor
        if cobit is not UNSET:
            field_dict["cobit"] = cobit
        if csa_star is not UNSET:
            field_dict["csa_star"] = csa_star
        if jericho_forum_comm is not UNSET:
            field_dict["jericho_forum_comm"] = jericho_forum_comm
        if sox is not UNSET:
            field_dict["sox"] = sox
        if cjis is not UNSET:
            field_dict["cjis"] = cjis
        if isae_3402 is not UNSET:
            field_dict["isae_3402"] = isae_3402
        if input_data_types is not UNSET:
            field_dict["input_data_types"] = input_data_types
        if output_data_types is not UNSET:
            field_dict["output_data_types"] = output_data_types
        if consumption_modes is not UNSET:
            field_dict["consumption_modes"] = consumption_modes
        if genai_types is not UNSET:
            field_dict["genai_types"] = genai_types
        if data_used_in_models is not UNSET:
            field_dict["data_used_in_models"] = data_used_in_models
        if allows_fine_tuning is not UNSET:
            field_dict["allows_fine_tuning"] = allows_fine_tuning
        if has_marketplace is not UNSET:
            field_dict["has_marketplace"] = has_marketplace
        if input_monitoring_and_review is not UNSET:
            field_dict["input_monitoring_and_review"] = input_monitoring_and_review
        if security_guardrails is not UNSET:
            field_dict["security_guardrails"] = security_guardrails
        if copyright_indemnity is not UNSET:
            field_dict["copyright_indemnity"] = copyright_indemnity
        if rbac is not UNSET:
            field_dict["rbac"] = rbac
        if mfa is not UNSET:
            field_dict["mfa"] = mfa
        if password_policy is not UNSET:
            field_dict["password_policy"] = password_policy
        if ip_based_restrictions is not UNSET:
            field_dict["ip_based_restrictions"] = ip_based_restrictions
        if saml is not UNSET:
            field_dict["saml"] = saml
        if quantum_readiness is not UNSET:
            field_dict["quantum_readiness"] = quantum_readiness
        if pqc_method is not UNSET:
            field_dict["pqc_method"] = pqc_method

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_spoof_risk_level(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        spoof_risk_level = _parse_spoof_risk_level(d.pop("spoof_risk_level", UNSET))

        def _parse_disaster_recovery(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        disaster_recovery = _parse_disaster_recovery(d.pop("disaster_recovery", UNSET))

        def _parse_encryption_in_transit(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        encryption_in_transit = _parse_encryption_in_transit(d.pop("encryption_in_transit", UNSET))

        def _parse_native_data_classification(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        native_data_classification = _parse_native_data_classification(d.pop("native_data_classification", UNSET))

        def _parse_audit_log(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        audit_log = _parse_audit_log(d.pop("audit_log", UNSET))

        def _parse_data_retention(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        data_retention = _parse_data_retention(d.pop("data_retention", UNSET))

        def _parse_file_content_sharing(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        file_content_sharing = _parse_file_content_sharing(d.pop("file_content_sharing", UNSET))

        def _parse_session_timeout(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        session_timeout = _parse_session_timeout(d.pop("session_timeout", UNSET))

        def _parse_encryption_at_rest(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        encryption_at_rest = _parse_encryption_at_rest(d.pop("encryption_at_rest", UNSET))

        def _parse_encryption_strength_at_rest(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        encryption_strength_at_rest = _parse_encryption_strength_at_rest(d.pop("encryption_strength_at_rest", UNSET))

        def _parse_protected_from_downgrade_attacks(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        protected_from_downgrade_attacks = _parse_protected_from_downgrade_attacks(
            d.pop("protected_from_downgrade_attacks", UNSET)
        )

        def _parse_privacy_policy(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        privacy_policy = _parse_privacy_policy(d.pop("privacy_policy", UNSET))

        def _parse_data_ownership(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        data_ownership = _parse_data_ownership(d.pop("data_ownership", UNSET))

        def _parse_third_party_data_sharing(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        third_party_data_sharing = _parse_third_party_data_sharing(d.pop("third_party_data_sharing", UNSET))

        def _parse_http_security_headers(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        http_security_headers = _parse_http_security_headers(d.pop("http_security_headers", UNSET))

        def _parse_terms_and_conditions(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        terms_and_conditions = _parse_terms_and_conditions(d.pop("terms_and_conditions", UNSET))

        def _parse_iso_9000(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        iso_9000 = _parse_iso_9000(d.pop("iso_9000", UNSET))

        def _parse_iso_9001(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        iso_9001 = _parse_iso_9001(d.pop("iso_9001", UNSET))

        def _parse_iso_27001(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        iso_27001 = _parse_iso_27001(d.pop("iso_27001", UNSET))

        def _parse_iso_27002(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        iso_27002 = _parse_iso_27002(d.pop("iso_27002", UNSET))

        def _parse_iso_27017(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        iso_27017 = _parse_iso_27017(d.pop("iso_27017", UNSET))

        def _parse_iso_27018(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        iso_27018 = _parse_iso_27018(d.pop("iso_27018", UNSET))

        def _parse_soc1(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        soc1 = _parse_soc1(d.pop("soc1", UNSET))

        def _parse_soc2(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        soc2 = _parse_soc2(d.pop("soc2", UNSET))

        def _parse_pci(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        pci = _parse_pci(d.pop("pci", UNSET))

        def _parse_hipaa(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        hipaa = _parse_hipaa(d.pop("hipaa", UNSET))

        def _parse_gdpr(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        gdpr = _parse_gdpr(d.pop("gdpr", UNSET))

        def _parse_ferpa(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        ferpa = _parse_ferpa(d.pop("ferpa", UNSET))

        def _parse_coppa(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        coppa = _parse_coppa(d.pop("coppa", UNSET))

        def _parse_finra(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        finra = _parse_finra(d.pop("finra", UNSET))

        def _parse_ffiec(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        ffiec = _parse_ffiec(d.pop("ffiec", UNSET))

        def _parse_glba(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        glba = _parse_glba(d.pop("glba", UNSET))

        def _parse_gapp(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        gapp = _parse_gapp(d.pop("gapp", UNSET))

        def _parse_itar(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        itar = _parse_itar(d.pop("itar", UNSET))

        def _parse_hitrust_csf(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        hitrust_csf = _parse_hitrust_csf(d.pop("hitrust_csf", UNSET))

        def _parse_trustarc(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        trustarc = _parse_trustarc(d.pop("trustarc", UNSET))

        def _parse_fedramp(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        fedramp = _parse_fedramp(d.pop("fedramp", UNSET))

        def _parse_c5(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        c5 = _parse_c5(d.pop("c5", UNSET))

        def _parse_ssae18(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        ssae18 = _parse_ssae18(d.pop("ssae18", UNSET))

        def _parse_nist_sp_80053(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        nist_sp_80053 = _parse_nist_sp_80053(d.pop("nist_sp_80053", UNSET))

        def _parse_fisma(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        fisma = _parse_fisma(d.pop("fisma", UNSET))

        def _parse_privacy_mark_japan(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        privacy_mark_japan = _parse_privacy_mark_japan(d.pop("privacy_mark_japan", UNSET))

        def _parse_privacy_shield(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        privacy_shield = _parse_privacy_shield(d.pop("privacy_shield", UNSET))

        def _parse_safe_harbor(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        safe_harbor = _parse_safe_harbor(d.pop("safe_harbor", UNSET))

        def _parse_cobit(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        cobit = _parse_cobit(d.pop("cobit", UNSET))

        def _parse_csa_star(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        csa_star = _parse_csa_star(d.pop("csa_star", UNSET))

        def _parse_jericho_forum_comm(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        jericho_forum_comm = _parse_jericho_forum_comm(d.pop("jericho_forum_comm", UNSET))

        def _parse_sox(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        sox = _parse_sox(d.pop("sox", UNSET))

        def _parse_cjis(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        cjis = _parse_cjis(d.pop("cjis", UNSET))

        def _parse_isae_3402(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        isae_3402 = _parse_isae_3402(d.pop("isae_3402", UNSET))

        def _parse_input_data_types(data: object) -> list[str] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                input_data_types_type_0 = cast(list[str], data)

                return input_data_types_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[str] | None | Unset, data)

        input_data_types = _parse_input_data_types(d.pop("input_data_types", UNSET))

        def _parse_output_data_types(data: object) -> list[str] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                output_data_types_type_0 = cast(list[str], data)

                return output_data_types_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[str] | None | Unset, data)

        output_data_types = _parse_output_data_types(d.pop("output_data_types", UNSET))

        def _parse_consumption_modes(data: object) -> list[str] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                consumption_modes_type_0 = cast(list[str], data)

                return consumption_modes_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[str] | None | Unset, data)

        consumption_modes = _parse_consumption_modes(d.pop("consumption_modes", UNSET))

        def _parse_genai_types(data: object) -> list[str] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                genai_types_type_0 = cast(list[str], data)

                return genai_types_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[str] | None | Unset, data)

        genai_types = _parse_genai_types(d.pop("genai_types", UNSET))

        def _parse_data_used_in_models(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        data_used_in_models = _parse_data_used_in_models(d.pop("data_used_in_models", UNSET))

        def _parse_allows_fine_tuning(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        allows_fine_tuning = _parse_allows_fine_tuning(d.pop("allows_fine_tuning", UNSET))

        def _parse_has_marketplace(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        has_marketplace = _parse_has_marketplace(d.pop("has_marketplace", UNSET))

        def _parse_input_monitoring_and_review(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        input_monitoring_and_review = _parse_input_monitoring_and_review(d.pop("input_monitoring_and_review", UNSET))

        def _parse_security_guardrails(data: object) -> list[str] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                security_guardrails_type_0 = cast(list[str], data)

                return security_guardrails_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[str] | None | Unset, data)

        security_guardrails = _parse_security_guardrails(d.pop("security_guardrails", UNSET))

        def _parse_copyright_indemnity(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        copyright_indemnity = _parse_copyright_indemnity(d.pop("copyright_indemnity", UNSET))

        def _parse_rbac(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        rbac = _parse_rbac(d.pop("rbac", UNSET))

        def _parse_mfa(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        mfa = _parse_mfa(d.pop("mfa", UNSET))

        def _parse_password_policy(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        password_policy = _parse_password_policy(d.pop("password_policy", UNSET))

        def _parse_ip_based_restrictions(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        ip_based_restrictions = _parse_ip_based_restrictions(d.pop("ip_based_restrictions", UNSET))

        def _parse_saml(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        saml = _parse_saml(d.pop("saml", UNSET))

        def _parse_quantum_readiness(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        quantum_readiness = _parse_quantum_readiness(d.pop("quantum_readiness", UNSET))

        def _parse_pqc_method(data: object) -> list[str] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                pqc_method_type_0 = cast(list[str], data)

                return pqc_method_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[str] | None | Unset, data)

        pqc_method = _parse_pqc_method(d.pop("pqc_method", UNSET))

        catalog_attributes = cls(
            spoof_risk_level=spoof_risk_level,
            disaster_recovery=disaster_recovery,
            encryption_in_transit=encryption_in_transit,
            native_data_classification=native_data_classification,
            audit_log=audit_log,
            data_retention=data_retention,
            file_content_sharing=file_content_sharing,
            session_timeout=session_timeout,
            encryption_at_rest=encryption_at_rest,
            encryption_strength_at_rest=encryption_strength_at_rest,
            protected_from_downgrade_attacks=protected_from_downgrade_attacks,
            privacy_policy=privacy_policy,
            data_ownership=data_ownership,
            third_party_data_sharing=third_party_data_sharing,
            http_security_headers=http_security_headers,
            terms_and_conditions=terms_and_conditions,
            iso_9000=iso_9000,
            iso_9001=iso_9001,
            iso_27001=iso_27001,
            iso_27002=iso_27002,
            iso_27017=iso_27017,
            iso_27018=iso_27018,
            soc1=soc1,
            soc2=soc2,
            pci=pci,
            hipaa=hipaa,
            gdpr=gdpr,
            ferpa=ferpa,
            coppa=coppa,
            finra=finra,
            ffiec=ffiec,
            glba=glba,
            gapp=gapp,
            itar=itar,
            hitrust_csf=hitrust_csf,
            trustarc=trustarc,
            fedramp=fedramp,
            c5=c5,
            ssae18=ssae18,
            nist_sp_80053=nist_sp_80053,
            fisma=fisma,
            privacy_mark_japan=privacy_mark_japan,
            privacy_shield=privacy_shield,
            safe_harbor=safe_harbor,
            cobit=cobit,
            csa_star=csa_star,
            jericho_forum_comm=jericho_forum_comm,
            sox=sox,
            cjis=cjis,
            isae_3402=isae_3402,
            input_data_types=input_data_types,
            output_data_types=output_data_types,
            consumption_modes=consumption_modes,
            genai_types=genai_types,
            data_used_in_models=data_used_in_models,
            allows_fine_tuning=allows_fine_tuning,
            has_marketplace=has_marketplace,
            input_monitoring_and_review=input_monitoring_and_review,
            security_guardrails=security_guardrails,
            copyright_indemnity=copyright_indemnity,
            rbac=rbac,
            mfa=mfa,
            password_policy=password_policy,
            ip_based_restrictions=ip_based_restrictions,
            saml=saml,
            quantum_readiness=quantum_readiness,
            pqc_method=pqc_method,
        )

        catalog_attributes.additional_properties = d
        return catalog_attributes

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
