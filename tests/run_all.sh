#!/usr/bin/env bash
set -euo pipefail

python source_rule_audit_v3.py
python source_feedback_audit.py
python ic_primitive_port_verifier.py
python ic_gamma_tree_copy_demo.py
python tests/size_family_integrity.py
python ic_size_family_audit.py --verify-report results/size_family_audit.json
python ic_reduced_package_copy_demo.py
python ic_tree_erase_demo.py
python source_ic_structure_encoding.py
python ic_unary_operational_fragment.py
python ic_signed_unary_comparator.py
python ic_composable_signed_difference.py
python ic_tagged_unary_case.py
python ic_signed_branch_pruning.py
python ic_signed_sum_selector.py
python ic_three_way_selector.py
python ic_typed_entry_rules.py
python ic_bounded_execution.py
python ic_research_artifacts.py
python ic_research_pipeline.py
python ic_research_pipeline.py --verify-report results/native_ic_research.json.gz
python lafont_ic_macro_builder.py
python ic_package_codec.py
python ic_coherent_output_decoder.py
python tests/coherent_artifact_integrity.py
python ic_fast_reducer.py
python ic_coherent_certificates.py --verify-report results/coherent_rule_certificates.json.gz --trace results/coherent_rule_certificates.ictrace.gz
python ic_coherent_contexts.py
python tests/program_code_bridge_integrity.py
python ic_program_code_bridge.py --verify-report results/program_code_bridge.json.gz --trace results/program_code_bridge.ictrace.gz
python tests/safe_program_activation_integrity.py
python ic_safe_program_activation.py --verify-report results/safe_program_activation.json.gz --trace results/safe_program_activation.ictrace.gz
python tests/typed_programs_integrity.py
python tests/schedule_audit_integrity.py
python tests/composition_evidence_integrity.py
python ic_composition_certificates.py --verify-report results/composition_certificates.json.gz --trace results/composition_certificates.ictrace.gz
python tests/component_candidates_integrity.py
python tests/observation_contracts_integrity.py
python tests/discovered_programs_integrity.py
python tests/component_witnesses_integrity.py
python tests/multitask_discovery_integrity.py
python ic_multitask_discovery.py --verify-report results/multitask_discovery.json.gz --trace results/multitask_discovery.ictrace.gz
python tests/structure_library_integrity.py
python tests/structure_capsules_integrity.py
python tests/reuse_benchmarks_integrity.py
python tests/structure_reuse_integrity.py
python ic_structure_reuse.py --verify-report results/structure_reuse.json.gz --library results/structure_library.json.gz --trace results/structure_reuse.ictrace.gz
python tests/native_control_packets_integrity.py
python tests/result_controlled_library_integrity.py
python tests/result_controlled_evidence_integrity.py
python tests/result_controlled_composition_integrity.py
python tests/result_controlled_execution_integrity.py
python tests/result_controlled_parallel_integrity.py
python tests/result_controlled_trace_integrity.py
python ic_result_controlled_execution.py --verify-report results/result_controlled_execution.json.gz --library results/structure_library.json.gz --trace results/result_controlled_execution.ictrace.gz
python ic_coherent_feedback.py --input 0
python ic_coherent_feedback.py --input 2
python ic_coherent_feedback.py --verify-report results/coherent_feedback_81.json.gz --replay-trace results/coherent_feedback_81.ictrace.gz --verify-final results/coherent_feedback_81.final.json.gz
python lafont_sigma_width_audit.py
python lafont_phi_psi_split.py
python lafont_macro_budget_v2.py
