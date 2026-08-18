import { useParams } from "react-router-dom";
import DynamicLegalPage from "@/pages/legal/DynamicLegalPage";

// Renders any admin-created custom page at /pages/:slug
export default function PublicPage() {
  const { slug } = useParams();
  return <DynamicLegalPage key={slug} slug={slug} />;
}
