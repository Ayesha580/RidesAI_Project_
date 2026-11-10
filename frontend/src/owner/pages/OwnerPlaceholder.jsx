import { useParams, useLocation } from "react-router-dom";
import OwnerLayout from "../components/OwnerLayout";
import { moduleIcon, moduleLabel } from "../../constants/modules";

export default function OwnerPlaceholder() {
  const { moduleKey } = useParams();
  const { pathname } = useLocation();
  const key = moduleKey || pathname.split("/").pop().replace(/-/g, "_");
  return (
    <OwnerLayout title={moduleLabel(key)}>
      <div className="ad-empty">
        <span>{moduleIcon(key)}</span>
        <h3>{moduleLabel(key)}</h3>
        <p>This page is coming soon.</p>
      </div>
    </OwnerLayout>
  );
}