let resultadoOriginal = null;

function formatarDataHora(dataIso) {
  if (!dataIso) {
    return "-";
  }

  const data = new Date(dataIso);
  return data.toLocaleString("pt-BR");
}

function criarBadgeStatus(status) {
  if (status === "ok") {
    return '<span class="badge badge-ok">OK</span>';
  }

  return '<span class="badge badge-error">ERRO</span>';
}

function preencherResumo(resultado) {
  document.getElementById("executado-em").textContent = formatarDataHora(resultado.executed_at);
  document.getElementById("total-convenios").textContent = resultado.total_convenios ?? 0;
  document.getElementById("success-count").textContent = resultado.success_count ?? 0;
  document.getElementById("error-count").textContent = resultado.error_count ?? 0;
  document.getElementById("records-count").textContent = resultado.records_count ?? 0;
}

function limparResumo() {
  document.getElementById("executado-em").textContent = "-";
  document.getElementById("total-convenios").textContent = "0";
  document.getElementById("success-count").textContent = "0";
  document.getElementById("error-count").textContent = "0";
  document.getElementById("records-count").textContent = "0";
}

function preencherTabela(resultado, termoFiltro = "") {
  const tbody = document.getElementById("tabela-body");
  const statusBox = document.getElementById("status-box");
  tbody.innerHTML = "";

  const filtro = termoFiltro.trim().toLowerCase();
  let linhasRenderizadas = 0;

  resultado.convenios.forEach((convenio) => {
    const nomeConvenio = convenio.convenio_nome ?? "-";

    if (convenio.status !== "ok" || !convenio.dados || convenio.dados.length === 0) {
      const textoBusca = `${nomeConvenio} ${convenio.erro ?? ""}`.toLowerCase();

      if (filtro && !textoBusca.includes(filtro)) {
        return;
      }

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${nomeConvenio}</td>
        <td>${criarBadgeStatus(convenio.status)}</td>
        <td class="muted">-</td>
        <td class="muted">-</td>
        <td class="muted">-</td>
        <td class="erro-texto">${convenio.erro ?? "-"}</td>
      `;
      tbody.appendChild(tr);
      linhasRenderizadas += 1;
      return;
    }

    convenio.dados.forEach((item) => {
      const folha = item.folha ?? "-";
      const mesAtual = item.mes_atual ?? "-";
      const dataCorte = item.data_corte ?? "-";

      const textoBusca = `${nomeConvenio} ${folha} ${mesAtual} ${dataCorte}`.toLowerCase();

      if (filtro && !textoBusca.includes(filtro)) {
        return;
      }

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${nomeConvenio}</td>
        <td>${criarBadgeStatus(convenio.status)}</td>
        <td>${folha}</td>
        <td>${mesAtual}</td>
        <td>${dataCorte}</td>
        <td class="muted">${convenio.erro ?? "-"}</td>
      `;
      tbody.appendChild(tr);
      linhasRenderizadas += 1;
    });
  });

  statusBox.textContent = `Exibindo ${linhasRenderizadas} linha(s).`;
}

async function carregarDados() {
  const statusBox = document.getElementById("status-box");
  const processadora = document.getElementById("select-processadora").value;
  statusBox.textContent = "Carregando dados...";

  try {
    const resposta = await fetch(
      `http://localhost:8000/coletas/${processadora}/ultimo_resultado`
    );

    if (!resposta.ok) {
      throw new Error(`Falha ao carregar dados. Status HTTP: ${resposta.status}`);
    }

    const resultado = await resposta.json();

    if (resultado.status === "empty") {
      resultadoOriginal = null;
      document.getElementById("tabela-body").innerHTML = "";
      limparResumo();
      statusBox.textContent = "Nenhuma execução encontrada para essa processadora.";
      return;
    }

    resultadoOriginal = resultado;
    preencherResumo(resultado);
    preencherTabela(resultado, document.getElementById("filtro-convenio").value);
  } catch (erro) {
    console.error(erro);
    statusBox.textContent = `Erro ao carregar dados: ${erro.message}`;
  }
}

async function executarColeta() {
  const btnColetar = document.getElementById("btn-coletar");
  const statusBox = document.getElementById("status-box");
  const processadora = document.getElementById("select-processadora").value;

  btnColetar.disabled = true;
  btnColetar.textContent = "Coletando...";
  statusBox.textContent = `Executando coleta da processadora ${processadora}...`;

  try {
    const resposta = await fetch(
      `http://localhost:8000/coletas/${processadora}/executar`,
      {
        method: "POST",
      }
    );

    if (!resposta.ok) {
      throw new Error(`Falha ao executar coleta. Status HTTP: ${resposta.status}`);
    }

    await carregarDados();
  } catch (erro) {
    console.error(erro);
    statusBox.textContent = `Erro ao executar coleta: ${erro.message}`;
    alert(`Erro ao executar coleta: ${erro.message}`);
  } finally {
    btnColetar.disabled = false;
    btnColetar.textContent = "Coletar agora";
  }
}

function configurarEventos() {
  const inputFiltro = document.getElementById("filtro-convenio");
  const btnRecarregar = document.getElementById("btn-recarregar");
  const btnColetar = document.getElementById("btn-coletar");
  const selectProcessadora = document.getElementById("select-processadora");

  inputFiltro.addEventListener("input", () => {
    if (!resultadoOriginal) {
      return;
    }

    preencherTabela(resultadoOriginal, inputFiltro.value);
  });

  btnRecarregar.addEventListener("click", async () => {
    await carregarDados();
  });

  btnColetar.addEventListener("click", async () => {
    await executarColeta();
  });

  selectProcessadora.addEventListener("change", async () => {
    await carregarDados();
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  configurarEventos();
  await carregarDados();

  setInterval(() => {
    carregarDados();
  }, 30000);
});