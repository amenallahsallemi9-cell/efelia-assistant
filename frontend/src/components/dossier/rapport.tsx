import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Rapport de l'agent (Markdown). Le HTML brut n'est jamais interprété. */
export function Rapport({ markdown }: { markdown: string }) {
  return (
    <article className="rapport max-w-prose">
      <Markdown remarkPlugins={[remarkGfm]} skipHtml>
        {markdown}
      </Markdown>
    </article>
  );
}
