import FarmOverviewClient from "@/components/FarmOverviewClient";
import { allSummaries, getFarm24hProfile, getFarmWeather } from "@/lib/data";

export default function OverviewPage() {
  const sums = allSummaries();
  const weatherData = {
    kelmarsh: getFarmWeather("kelmarsh"),
    penmanshiel: getFarmWeather("penmanshiel"),
  };
  const profileData = {
    kelmarsh: getFarm24hProfile("kelmarsh"),
    penmanshiel: getFarm24hProfile("penmanshiel"),
  };

  return (
    <div className="page">
      <FarmOverviewClient windows={sums} weatherData={weatherData} profileData={profileData} />
    </div>
  );
}

