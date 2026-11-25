import React from "react";
import { Layers, Menu, X } from "lucide-react";

interface TopHeaderProps {
  recorded?: boolean;
  onToggleMobileMenu?: () => void;
  isMobileMenuOpen?: boolean;
}

export const TopHeader: React.FC<TopHeaderProps> = ({
  recorded = false,
  onToggleMobileMenu,
  isMobileMenuOpen,
}) => {
  return (
    <header className="h-[68px] sm:h-[72px] bg-[#0B0F14] border-b border-white/[0.075] px-4 sm:px-6 lg:px-8 flex items-center justify-between sticky top-0 z-50">
      {/* Left: Logo & Hackathon Context */}
      <div className="flex items-center space-x-3 sm:space-x-4">
        {/* Mobile menu hamburger toggle */}
        <button
          onClick={onToggleMobileMenu}
          className="lg:hidden p-1.5 rounded-md text-[#848B95] hover:text-white hover:bg-white/[0.05] transition-colors"
          aria-label="Toggle Navigation Menu"
          aria-expanded={!!isMobileMenuOpen}
          aria-controls="dashboard-navigation"
        >
          {isMobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>

        {/* BlastGate Angular Chevron Mark */}
        <div className="flex items-center space-x-2.5">
          <svg
            width="22"
            height="22"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className="shrink-0"
          >
            <path
              d="M3 20L10.5 4H14.5L7 20H3Z"
              fill="#D8A955"
            />
            <path
              d="M13 20L20.5 4H16.5L9 20H13Z"
              fill="#D8A955"
              fillOpacity="0.45"
            />
          </svg>
          <span className="font-sans font-semibold text-base sm:text-lg tracking-tight text-[#F5F4F1]">
            BlastGate
          </span>
        </div>

        {/* Hackathon Context Label */}
        <span className="text-xs text-[#848B95] font-normal tracking-wide hidden sm:inline ml-3 pl-3 sm:ml-4 sm:pl-4 border-l border-white/[0.08]">
          AWS Startup Hackathon
        </span>
      </div>

      {/* Right: Operational Status Badges */}
      <div className="flex items-center space-x-2 sm:space-x-3">
        {/* Simulated Data Badge */}
        <div className="flex items-center space-x-1.5 py-1 text-[#A1A8B2] text-xs font-medium tracking-wide">
          <Layers className="w-3.5 h-3.5 shrink-0" />
          <span>{recorded ? "Recorded AWS Evidence" : "Simulated Data"}</span>
        </div>


      </div>
    </header>
  );
};
