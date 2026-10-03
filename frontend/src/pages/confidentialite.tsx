export function PageConfidentialite() {
  return (
    <article className="rapport mx-auto max-w-prose">
      <h1>Confidentialité et données personnelles</h1>
      <p>
        Cette application est un projet étudiant indépendant, <strong>non affilié à EFELIA</strong>.
        Elle vérifie la recevabilité d'un dossier de candidature à la Bourse Excellence ; le
        règlement officiel fait foi.
      </p>
      <h2>Données traitées</h2>
      <ul>
        <li>Les informations de la fiche (nom, prénom, e-mail, formation, situation déclarée).</li>
        <li>Le dossier PDF, stocké sous un nom aléatoire dans un espace dédié.</li>
        <li>Le texte des pièces ordinaires et les informations qui en sont extraites.</li>
      </ul>
      <h2>Justificatifs sensibles</h2>
      <p>
        Les justificatifs sociaux (avis d'imposition, relevés bancaires, bulletins de salaire…)
        et de handicap (CMI, RQTH, MDPH, certificats médicaux) sont <strong>seulement détectés</strong> :
        leur texte n'est ni conservé, ni envoyé au modèle d'IA, ni indexé, et leur aperçu est masqué.
      </p>
      <h2>Intelligence artificielle</h2>
      <p>
        Le texte des pièces ordinaires est transmis au fournisseur du modèle de langage (Cohere)
        pour l'extraction d'informations et l'instruction. Votre adresse e-mail ne lui est jamais
        transmise. Le statut final est toujours calculé par les règles du règlement, jamais par l'IA
        seule, et l'outil ne prédit jamais la décision du jury.
      </p>
      <h2>Conservation et effacement</h2>
      <p>
        Les dossiers sont supprimés automatiquement après la durée de conservation configurée. Vous
        pouvez supprimer votre dossier à tout moment depuis sa page : le fichier, le texte, les
        données extraites, les index de recherche et la trace de l'agent sont alors effacés.
      </p>
    </article>
  );
}
