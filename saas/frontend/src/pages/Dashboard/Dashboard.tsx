import { useNavigate } from "react-router-dom";
import { Search, CalendarClock, GitPullRequest } from "lucide-react";
import { Button } from "../../components/shared/Form";

const CARDS = [
  {
    icon: Search,
    title: "Run your first pentest",
    description: "Find vulnerabilities in your apps and APIs with a security test.",
    cta: "Start Pentest",
    to: "/pentests",
  },
  {
    icon: CalendarClock,
    title: "Schedule pentests",
    description: "Automate recurring security tests on your own schedule.",
    cta: "Set Up Schedule",
    to: "/pentests",
  },
  {
    icon: GitPullRequest,
    title: "Enable PR reviews",
    description: "Catch vulnerabilities in every PR with checks that block risky merges.",
    cta: "Enable Reviews",
    to: "/pr-reviews",
  },
];

export default function Dashboard() {
  const navigate = useNavigate();

  return (
    <div className="mx-auto max-w-4xl py-12 text-center">
      <h1 className="text-3xl font-semibold text-white">Get started with Strix</h1>
      <p className="mt-3 text-[#888]">Run pentests against your apps and APIs to uncover and fix vulnerabilities.</p>

      <div className="mt-10 grid grid-cols-1 gap-4 sm:grid-cols-3">
        {CARDS.map((card) => (
          <div key={card.title} className="flex flex-col items-center rounded-xl border border-[#222] bg-[rgba(255,255,255,0.02)] p-6">
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl border border-[#2a2a2a]">
              <card.icon size={20} className="text-white" />
            </div>
            <h3 className="mb-1.5 font-semibold text-white">{card.title}</h3>
            <p className="mb-5 flex-1 text-sm text-[#888]">{card.description}</p>
            <Button className="w-full" onClick={() => navigate(card.to)}>
              {card.cta}
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}
