import React, { useState } from "react";

import {

  ShieldCheck,

  ChevronDown,

  ChevronUp,

  Search,

  AlertTriangle,

  Check,

} from "lucide-react";

import { SecurityRule } from "@/types";



interface SecurityRulesSectionProps {

  rules: SecurityRule[];

}



export const SecurityRulesSection: React.FC<SecurityRulesSectionProps> = ({ rules }) => {

  const [expandedRuleId, setExpandedRuleId] = useState<string | null>("R1");

  const [searchQuery, setSearchQuery] = useState("");



  const toggleExpand = (ruleId: string) => {

    setExpandedRuleId(expandedRuleId === ruleId ? null : ruleId);

  };



  const filteredRules = rules.filter(

    (r) =>

      r.rule_id.toLowerCase().includes(searchQuery.toLowerCase()) ||

      r.name.toLowerCase().includes(searchQuery.toLowerCase()) ||

      r.plain_meaning.toLowerCase().includes(searchQuery.toLowerCase()) ||

      r.enforcement_layer.toLowerCase().includes(searchQuery.toLowerCase())

  );



  return (

    <div className="space-y-5">

      {/* Top Banner */}

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[#11161D] p-5 rounded-[14px] border border-white/[0.075]">

        <div>

          <h2 className="text-xl font-bold text-[#F5F4F1] flex items-center gap-2.5 tracking-tight font-serif">

            <ShieldCheck className="w-5 h-5 text-[#D8A955]" />

            Security Enforcement Panel (Rules R1–R8)

          </h2>

          <p className="text-xs text-[#848B95] mt-1">

            Deterministic, provable operational invariants enforced independently of model behavior.

          </p>

        </div>

        <div className="flex items-center gap-2">

          <span className="text-xs bg-[#D8A955]/10 text-[#D8A955] border border-[#D8A955]/30 font-medium px-3 py-1 rounded-full flex items-center gap-1.5">

            <Check className="w-3.5 h-3.5 text-emerald-400" />

            8 operational rules · canonical definitions

          </span>

        </div>

      </div>



      {/* Search Bar */}

      <div className="flex items-center justify-between bg-[#11161D] p-3 rounded-[12px] border border-white/[0.075]">

        <div className="relative w-full sm:w-80">

          <Search className="w-4 h-4 text-[#848B95] absolute left-3 top-2.5" />

          <input

            aria-label="Search security rules" type="text"

            placeholder="Search rules by ID, layer, or keyword..."

            value={searchQuery}

            onChange={(e) => setSearchQuery(e.target.value)}

            className="w-full pl-9 pr-3 py-1.5 text-xs rounded-[8px] bg-[#0B0F14] border border-white/[0.08] text-[#F5F4F1] placeholder-[#616874] focus:border-[#D8A955] focus:outline-none"

          />

        </div>

        <div className="text-xs text-[#848B95] hidden sm:block">

          Click any card to inspect plain-language rationale and test bindings.

        </div>

      </div>



      {/* Rules List / Cards */}

      <div className="space-y-3">

        {filteredRules.map((rule) => {

          const isExpanded = expandedRuleId === rule.rule_id;



          return (

            <div

              key={rule.rule_id}

              className={`rounded-[12px] border bg-[#11161D] transition-all ${

                isExpanded

                  ? "border-[#D8A955] ring-1 ring-[#D8A955]/20 bg-[#141922]"

                  : "border-white/[0.075] hover:border-white/[0.14]"

              }`}

            >

              {/* Collapsed Header */}

              <div

                onClick={() => toggleExpand(rule.rule_id)} role="button" tabIndex={0} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggleExpand(rule.rule_id); } } } aria-expanded={isExpanded}

                className="p-4 cursor-pointer flex items-center justify-between gap-3 select-none"

              >

                <div className="flex items-center space-x-3.5">

                  <div className="w-8 h-8 rounded-[8px] bg-[#D8A955]/10 border border-[#D8A955]/30 flex items-center justify-center font-mono font-bold text-xs text-[#D8A955] shrink-0">

                    {rule.rule_id}

                  </div>

                  <div>

                    <div className="flex items-center space-x-2">

                      <h3 className="text-sm font-semibold text-[#F5F4F1]">{rule.name}</h3>

                      <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-[#D8A955]/15 text-[#D8A955] border border-[#D8A955]/30">

                        {rule.status}

                      </span>

                      <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-white/[0.04] text-[#848B95] font-medium hidden md:inline border border-white/[0.06]">

                        {rule.enforcement_layer.split("&")[0]}

                      </span>

                    </div>

                    <p className="text-xs text-[#848B95] mt-1 line-clamp-1 leading-relaxed">

                      {rule.plain_meaning}

                    </p>

                  </div>

                </div>



                <div className="flex items-center space-x-3 shrink-0">

                  <span className="text-xs font-mono font-semibold text-emerald-400 bg-emerald-500/10 px-2.5 py-0.5 rounded border border-emerald-500/20 hidden sm:inline">

                    {rule.current_result}

                  </span>

                  {isExpanded ? (

                    <ChevronUp className="w-4 h-4 text-[#848B95]" />

                  ) : (

                    <ChevronDown className="w-4 h-4 text-[#848B95]" />

                  )}

                </div>

              </div>



              {/* Expanded Details Body */}

              {isExpanded && (

                <div className="px-5 pb-5 pt-3 border-t border-white/[0.06] space-y-4 text-xs">

                  {/* Plain Meaning Highlight Box */}

                  <div className="p-3.5 rounded-[10px] bg-[#1C1813] border border-[#D8A955]/30">

                    <span className="text-[11px] font-bold text-[#D8A955] uppercase tracking-wider block mb-1">

                      Plain-Language Human Meaning

                    </span>

                    <p className="text-xs text-[#F5F4F1] leading-relaxed">

                      {rule.plain_meaning}

                    </p>

                  </div>



                  {/* Security Objective & Enforcement Layer */}

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">

                    <div className="p-3.5 bg-[#161B22] rounded-[10px] border border-white/[0.06] space-y-1">

                      <span className="text-[11px] font-bold text-[#848B95] uppercase block">

                        Security Objective

                      </span>

                      <p className="text-xs text-[#B5B8BD] leading-relaxed">

                        {rule.security_objective}

                      </p>

                    </div>



                    <div className="p-3.5 bg-[#161B22] rounded-[10px] border border-white/[0.06] space-y-1">

                      <span className="text-[11px] font-bold text-[#848B95] uppercase block">

                        Enforcement Layer & Mechanism

                      </span>

                      <p className="text-xs text-[#B5B8BD] font-medium">

                        Layer: <span className="font-mono text-[#D8A955]">{rule.enforcement_layer}</span>

                      </p>

                      <p className="text-[11px] text-[#848B95] mt-1 font-mono leading-relaxed">

                        {rule.independent_mechanism}

                      </p>

                    </div>

                  </div>



                  {/* Allowed vs Forbidden Table */}

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">

                    <div className="p-3.5 bg-emerald-950/20 border border-emerald-500/20 rounded-[10px] space-y-1">

                      <span className="text-[11px] font-bold text-emerald-400 flex items-center gap-1">

                        <Check className="w-3.5 h-3.5" /> Allowed Behavior:

                      </span>

                      <p className="text-xs text-[#B5B8BD] leading-relaxed">

                        {rule.allowed_behavior}

                      </p>

                    </div>



                    <div className="p-3.5 bg-red-950/20 border border-red-500/20 rounded-[10px] space-y-1">

                      <span className="text-[11px] font-bold text-red-400 flex items-center gap-1">

                        <AlertTriangle className="w-3.5 h-3.5" /> Forbidden Behavior:

                      </span>

                      <p className="text-xs text-[#B5B8BD] leading-relaxed">

                        {rule.forbidden_behavior}

                      </p>

                    </div>

                  </div>



                  {/* Metadata: Expected Refusal Code & Test IDs */}

                  <div className="flex flex-wrap items-center justify-between gap-2 p-3 bg-[#161B22] rounded-[10px] border border-white/[0.06]">

                    <div className="flex items-center space-x-2">

                      <span className="text-[#848B95] font-semibold text-[11px]">Expected Refusal:</span>

                      <span className="font-mono text-[11px] font-bold text-red-400 bg-red-500/10 px-2 py-0.5 rounded border border-red-500/20">

                        {rule.expected_refusal_code}

                      </span>

                    </div>



                    <div className="flex items-center space-x-2">

                      <span className="text-[#848B95] font-semibold text-[11px]">Automated Test Contracts:</span>

                      <div className="flex items-center space-x-1">

                        {rule.test_ids.map((tid) => (

                          <span

                            key={tid}

                            className="font-mono text-[11px] bg-[#0B0F14] text-[#D8A955] border border-white/[0.08] px-1.5 py-0.5 rounded font-bold"

                          >

                            {tid}

                          </span>

                        ))}

                      </div>

                    </div>

                  </div>



                  {/* Evidence Summary */}

                  <div className="flex items-center justify-between text-[11px] text-[#848B95] pt-1">

                    <span>

                      <strong>Verification Evidence:</strong> {rule.evidence_summary}

                    </span>

                    <span className="font-mono text-emerald-400 font-bold">Local verification references</span>

                  </div>

                </div>

              )}

            </div>

          );

        })}



        {filteredRules.length === 0 && (

          <div className="p-8 text-center bg-[#11161D] rounded-[12px] border border-white/[0.075] text-xs text-[#848B95]">

            No rules matched your search query.

          </div>

        )}

      </div>

    </div>

  );

};

