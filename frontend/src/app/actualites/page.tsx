import { PageHeading, PublicPageLayout } from "@/components/PublicPageLayout";
import { PublicNewsList } from "@/components/PublicNewsList";

export default function NewsPage() {
  return <PublicPageLayout><PageHeading kicker="Actualités" title="Les nouvelles de FANAFODIKO" intro="Les annonces officielles seront publiées ici lorsqu’elles seront disponibles." /><section className="mx-auto max-w-6xl px-5 py-10 sm:px-8 sm:py-14"><PublicNewsList /></section></PublicPageLayout>;
}
