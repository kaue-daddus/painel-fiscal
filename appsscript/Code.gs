/**
 * Porta de entrada do painel com login Google (Apps Script Web App).
 * 1) Troque PAGES_URL pela URL do seu GitHub Pages (termina com /).
 * 2) Implantar > Nova implantação > Aplicativo da Web > Executar como: eu; Acesso: Qualquer pessoa na Daddus (domínio).
 */
const PAGES_URL = "https://SEU-USUARIO.github.io/painel-fiscal/";

function doGet() {
  const html = UrlFetchApp.fetch(PAGES_URL + "index.html").getContentText("UTF-8")
    // os dados continuam vindo do GitHub Pages; aqui só fixamos a URL absoluta
    .replace('window.PAINEL_DADOS_URL=window.PAINEL_DADOS_URL||"dados/";',
             'window.PAINEL_DADOS_URL="' + PAGES_URL + 'dados/";');
  return HtmlService.createHtmlOutput(html)
    .setTitle("Daddus · Panorama Fiscal dos Municípios")
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
    .addMetaTag("viewport", "width=device-width, initial-scale=1");
}

/** Opcional: espelho semanal da base no Google Drive (gatilho de tempo em Acionadores). */
function espelharNoDrive() {
  const pasta = DriveApp.getFoldersByName("Painel Fiscal - base").hasNext()
    ? DriveApp.getFoldersByName("Painel Fiscal - base").next()
    : DriveApp.createFolder("Painel Fiscal - base");
  ["dados/base.json.gz", "dados/meta.json", "index.html"].forEach(function (nome) {
    const blob = UrlFetchApp.fetch(PAGES_URL + nome).getBlob().setName(nome.replace("/", "_"));
    const antigos = pasta.getFilesByName(blob.getName());
    while (antigos.hasNext()) antigos.next().setTrashed(true);
    pasta.createFile(blob);
  });
}
