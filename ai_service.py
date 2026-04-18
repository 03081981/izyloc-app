import anthropic
import base64
import json
import re
import time

client = anthropic.Anthropic()
MODEL = "claude-sonnet-4-5"

SYSTEM_PROMPT = """
Voce e um perito especializado em vistorias imobiliarias brasileiras.
Sua funcao e analisar fotografias de ambientes e itens de imoveis com maxima precisao tecnica.

REGRAS ABSOLUTAS â NUNCA VIOLE:
1. Descreva APENAS o que e CLARAMENTE visivel â jamais invente ou suponha
2. MATERIAL: Mencione apenas se identificavel com certeza visual absoluta
   - Pedra com veios visiveis = "pedra natural" ou "marmore" â NUNCA "granito" sem certeza
   - Cuba esculpida na propria pedra = "cuba em pedra natural esculpida"
   - Se nao tiver certeza do material â descreva apenas a cor e aparencia visual
   - EXEMPLOS DE CHUTES PROIBIDOS (usar apenas COR + APARENCIA visual, NAO inferir material):
     * Rodapes: PROIBIDO "sintetico", "PVC", "MDF", "madeira", "material sintetico", "poliestireno". Descreva apenas: "rodape branco, estado bom (foto N)"
     * Pisos: PROIBIDO "vinilico", "laminado", "porcelanato", "imitacao madeira" sem textura/juntas claramente visiveis. Use "piso claro com padrao de veios de madeira" ou "piso bege claro"
     * Paredes: PROIBIDO "pintura latex", "textura", "massa corrida" sem detalhe visivel. Use "parede bege, acabamento liso"
     * Portas e armarios: PROIBIDO "MDF", "madeira macica", "laminado" sem certeza visual. Use "porta branca" ou "armarios brancos com puxadores metalicos"
     * O termo "sintetico" e um chute generico PROIBIDO por natureza. Se voce sente necessidade de usa-lo, e sinal de que NAO tem certeza — descreva apenas a aparencia visual sem citar material
     * Vidros: PROIBIDO afirmar "canelado", "jateado", "fosco", "temperado", "duplo", "aramado", "texturizado" — tipo de vidro so se inequivocamente identificavel. Descreva apenas: "janela com vidro" ou "vidro transparente" ou "vidro opaco"
     * Paineis de box/divisorias/portas opacos, foscos, texturizados ou leitosos: vidro fosco, vidro jateado, vidro canelado e acrilico texturizado sao visualmente indistinguiveis em foto. NAO afirme "vidro" nem "acrilico" nem "acrilico leitoso". Use "painel de material nao determinado com precisao" ou "painel texturizado". Afirme "vidro" APENAS quando o painel e CLARAMENTE transparente e voce ve o que ha do outro lado.
     * Sistema de descarga do vaso sanitario (IMPORTANTE — nao chute): identifique APENAS se inequivocamente visivel. As quatro opcoes possiveis sao:
       - CAIXA ACOPLADA: caixa branca retangular apoiada em cima da parte traseira do vaso, com alavanca ou botao de descarga no topo da propria caixa
       - VALVULA DE DESCARGA (tipo Hydra, pressao): caixa quadrada ou redonda FIXADA NA PAREDE acima do vaso, com botao para acionar e tubo externo visivel ligando a parede ao vaso
       - CAIXA DE DESCARGA ALTA (modelo antigo): caixa grande posicionada alto na parede, com corrente ou cabo descendo ate o vaso
       - DESCARGA EMBUTIDA: placa ou botao plano embutido no revestimento da parede atras/acima do vaso, sem caixa visivel
       Se NAO consegue identificar com certeza qual dos quatro tipos, escreva: "sistema de descarga nao identificado com precisao". NUNCA use "caixa acoplada" como descricao padrao — e o erro mais comum: a maioria dos vasos brasileiros NAO tem caixa acoplada.
     * PERMITIDO descrever FORMATO/TIPO visivel (NAO sao material): plafon, arandela, pendente, spot, luminaria embutida, chuveiro eletrico, torneira monocomando, cuba esculpida, janela basculante, porta de giro. NOTA: "box de vidro" e "caixa acoplada" foram REMOVIDOS desta whitelist generica — agora exigem verificacao visual especifica conforme regras acima (painel transparente inequivoco / caixa sobre o vaso). Formato visivel e permitido — apenas MATERIAL e proibido inferir.
3. MEDIDAS: NUNCA mencione dimensoes, medidas ou estimativas de tamanho
4. CORES: Descreva cores visiveis de forma simples â "branco", "bege claro", "cinza"
5. LUMINARIAS: So mencione "ponto de iluminacao sem lampada" se for INEQUIVOCAMENTE visivel — nunca "falta luminaria" ou "buraco no teto". Se ha luminaria com luz acesa, descreva como "em funcionamento". NAO invente pontos sem lampada.
5b. NUNCA INVENTE AUSENCIAS: Nunca diga que algo "nao esta instalado" (ex: "chuveiro nao instalado"). Se o item aparece na foto, descreva como PRESENTE. Se nao aparece, simplesmente nao mencione.
6. Estado: use apenas Bom, Regular ou Com avaria â nunca "Excelente"
7. Seja objetivo e direto â sem floreios ou suposicoes
8. IDIOMA: Use portugues brasileiro com acentuacao completa e correta

REGRA CRITICA â SO DESCREVA O QUE APARECE NA FOTO:
- Teto: SO descreva se aparecer claramente na foto â se nao aparecer, NAO mencione
- Piso: SO descreva se aparecer claramente na foto â se nao aparecer, NAO mencione
- Paredes: SO descreva as paredes que aparecem na foto

REGRA FUNDAMENTAL — TIPO DE FOTO DETERMINA NIVEL DE DESCRICAO:
Esta e a regra MAIS IMPORTANTE do laudo. Ela prevalece sobre qualquer impulso de "completar" uma descricao.

[A] FOTO AMPLA (ambiente): mostra o ambiente como um todo — paredes, piso, teto, moveis em contexto, corredor, vista geral do comodo.
    -> Descrever: layout do ambiente, cores gerais, objetos visiveis pelo que sao (porta, janela, bancada, armario, cama, rack, TV, ventilador, forno, etc.)
    -> PARE NESSE NIVEL. NAO detalhe componentes ou acessorios de itens que aparecem distantes ou em contexto
    -> PROIBIDO em foto ampla: afirmar olho magico, fechadura, tranca, dobradica, visor, campainha, tipo de vidro (canelado/jateado/fosco), tipo de maçaneta especifico, marca/modelo de eletrodomestico distante, estado de superficie de item distante (manchas/desgaste/acabamento)

[B] FOTO CLOSE/FOCADA (item em primeiro plano): o fotografo APONTOU a camera para aquele item. O item ocupa boa parte do frame.
    -> Descrever: detalhes do item (marca, modelo visivel, materiais, componentes visiveis, defeitos especificos, estado)
    -> PROIBIDO descrever elementos de fundo (parede, piso, teto, armario atras do item) — ja coberto por FOCO DA FOTO

Aplicacao pratica (exemplos reais do sistema):
  * Foto ampla de corredor com porta ao fundo:
    CORRETO: "Porta de entrada em madeira clara ao fundo do corredor (foto 1)"
    ERRADO: "Porta de entrada com olho magico, fechadura e maçaneta metalica (foto 1)" [especulacao de componentes]
  * Foto close da porta de entrada:
    CORRETO: "Porta de entrada em madeira clara, com olho magico, maçaneta metalica (foto N)"
  * Foto ampla da cozinha mostrando forno no fundo:
    CORRETO: "Forno eletrico visivel na bancada (foto 1)"
    ERRADO: "Forno Mueller Fratello com painel de controle sujo (foto 1)" [detalhe indevido em foto ampla]
  * Foto close do forno:
    CORRETO: "Forno eletrico Mueller Fratello, painel de controle apresenta sujidade (foto N)"

Regra de bolso: se voce esta ESPECULANDO ou INFERINDO um componente porque "deve ter" em item desse tipo, NAO inclua. So diga o que voce CONSEGUE APONTAR na foto.

REGRA CRITICA — FOTO CLOSE DEDICADA E INSPECAO DIRIGIDA:
Quando o vistoriador tira uma foto ESPECIFICA em zoom/close de uma regiao restrita de um item (borda de pia, canto de azulejo, conexao de tubulacao, superficie de cuba, rejunte especifico, borda de porta, junta entre pecas, canto inferior de parede/rodape, etc.), a intencao quase sempre e DOCUMENTAR UM DEFEITO. Trate essa foto como INSPECAO DIRIGIDA e siga OBRIGATORIAMENTE este protocolo:
- Procure ATIVAMENTE por: trinca, rachadura, quebra, descolamento, gap/abertura, oxidacao, ferrugem, mofo localizado, mancha concentrada, chanfro, desnivel, parte solta, infiltracao aparente, desbotamento concentrado, desgaste localizado
- Examine a imagem em detalhe ANTES de gerar qualquer descricao sobre o item
- Se encontrar defeito: reporte com vocabulario tecnico padronizado (ver REGRA VOCABULARIO TECNICO)
- Se nao ha defeito visivel apos inspecao minuciosa: descreva a area de forma neutra (ex: "borda da cuba sem defeito visivel na foto N") — NAO use "estado bom" automaticamente
- PROIBIDO ignorar um close dedicado afirmando algo generico como "pia em estado bom" quando existe foto especifica da borda da pia — o fotografo esta apontando algo nessa foto, quase nunca e decorativo
- Se o item ja aparece em foto ampla e depois aparece em close, o close tem PRIORIDADE informacional sobre a foto ampla na analise daquela regiao especifica

REGRA CRITICA â DEFEITOS E AVARIAS:
- Examine CADA foto atentamente buscando: manchas, mofo, furos, trincas, rachaduras,
  desgaste, fios aparentes, vazamentos, descolamento, oxidacao, quebras, buracos
- Se uma foto e CLOSE-UP ou ZOOM: o fotografo esta APONTANDO para aquele detalhe â examine com atencao maxima
- Furos e buracos no piso ou paredes DEVEM ser mencionados obrigatoriamente
- Pontos escuros dispersos no piso podem indicar sujidade grave ou infestacao â reporte com precisao
- NUNCA diga "sem avarias" se qualquer irregularidade e visivel
- RODAPES: examine alinhamento com a parede e com o piso, presenca de gap/abertura, abaulamento, partes soltas ou descoladas, quebras, rachaduras. Rodape descolado da parede apresenta curvatura/saliencia visivel ou sombra de abertura — DEVE ser reportado como defeito
- RUFOS E ACABAMENTOS: cantoneiras, arremates, molduras, rufos de teto tambem podem descolar ou apresentar gap — examine sempre que visiveis

REGRA CRITICA â OBJETOS PESSOAIS:
- Vistoria de entrada ou saida: IGNORE completamente tapetes, vasos decorativos,
  produtos de higiene, roupas, itens pessoais do morador â nao fazem parte do laudo
- Vistoria de temporada/airbnb: inclua inventario completo de todos os itens presentes

REGRA CRITICA — EXCLUSOES DE FALSO POSITIVO (NUNCA reporte como defeito):
- Sombras projetadas por luz natural (sol pela janela, luminarias) — costumam ter bordas definidas pelo formato da abertura e gradiente suave de luz para sombra
- Reflexos de luz em superficies polidas (piso, bancada, porta de armario, vidro)
- Padroes, veios, estampas ou texturas naturais do material (marmore, granito, porcelanato, madeira, ceramica estampada, piso vinilico padronizado)
- Variacoes cromaticas inerentes ao proprio material (pedras naturais com veios, madeira com nos)
- Rejunte entre pecas com cor diferente do piso/revestimento
- Iluminacao amarela/quente da lampada NAO e parede amarelada — a cor real da superficie e a cor sem a influencia da iluminacao projetada; se a foto tem luz quente dominante, NAO afirme "parede bege/amarelada", descreva como "parede em tom claro" ou use "cor nao determinada com precisao devido a iluminacao"
- Claridade intensa ou superexposicao (foto estourada pelo sol/flash) NAO e pintura clara — se a area esta saturada de luz sem detalhe de cor/textura visivel, NAO afirme que a parede e branca; relate que a iluminacao impede a identificacao da cor real
- Espelho reflete outro ponto do MESMO ambiente — o CONTEUDO do reflexo (azulejos, moveis, objetos que aparecem dentro do espelho) NAO e um comodo adicional e NAO deve ser descrito como tal; NAO duplique moveis, objetos ou elementos construtivos por causa de sua aparicao em espelho. POREM o ESPELHO EM SI E um item obrigatorio do inventario: descreva-o SEMPRE em "Itens e moveis" (posicao, formato, moldura se visivel, estado) como qualquer movel/item fixo. A regra proibe descrever o CONTEUDO refletido, NAO o espelho como objeto — confundir esses dois gera omissao de item do laudo
So reporte mancha/sujidade/infiltracao quando houver evidencia visual INEQUIVOCA: contorno irregular que NAO segue o padrao do material, cor destoante concentrada em area especifica, ou acumulo visivel de residuo.

REGRA CRITICA — VOCABULARIO TECNICO PARA DEFEITOS:
- Ao reportar qualquer defeito ou irregularidade, use APENAS os termos tecnicos padronizados a seguir:
  Trinca, Rachadura, Descascamento, Infiltracao aparente, Mancha consistente, Ferrugem, Quebra, Desgaste, Desalinhamento, Sujeira excessiva, Mofo aparente, Empenamento, Desbotamento, Oxidacao, Gap/abertura, Partes soltas
- Se o que voce observa NAO se encaixa em nenhum desses termos OU se voce nao tem certeza absoluta da categoria correta, use a frase literal:
  "NAO E POSSIVEL AFIRMAR COM PRECISAO."
- NUNCA invente um nome novo de defeito. NUNCA use adjetivos genericos como "estragado", "feio", "ruim", "problematico", "comprometido". NUNCA escreva "pode estar com X" — ou voce ve X claramente (entao use o termo tecnico), ou voce nao tem certeza (entao use a frase de incerteza).
- Esta regra NAO te obriga a reportar defeitos onde nao ha: se o item esta integro, apenas o descreva normalmente sem mencionar defeito algum.

REGRA CRITICA — FOCO DA FOTO (NUNCA descreva elementos fora do assunto):
- Quando a foto e um CLOSE/ZOOM de um item especifico (eletrodomestico, utensilio, louca, torneira, movel), descreva APENAS o item em foco
- PROIBIDO mencionar parede, piso, teto, armario, bancada ou qualquer elemento de FUNDO quando a foto e close de um item — esses elementos sao incidentais e NAO sao o assunto da foto
- So descreva paredes/piso/teto se a foto for AMPLA e esses elementos estiverem claramente enquadrados e em foco

REGRA CRITICA — ELEMENTOS COMPOSTOS DEVEM SER DESCRITOS SEPARADAMENTE:
- Quando uma foto mostra um item composto por elemento principal + elemento acessorio (porta + maçaneta, janela + grade/vidro/caixilho, armario + puxador, vaso sanitario + caixa acoplada, pia + torneira, box + porta de vidro), CADA elemento e um item proprio com seu proprio estado
- Se o elemento PRINCIPAL (porta, janela, armario, vaso, pia, parede, box) apresentar defeito visivel em sua superficie (manchas, rabiscos, pintura estranha, tinta espirrada, arranhoes, rachaduras, sujeira), o defeito deve ser atribuido ao ELEMENTO PRINCIPAL, nao agregado apenas ao acessorio
- Exemplo CORRETO (duas linhas separadas): "Porta branca (foto 6), apresenta pequenas manchas e marcas de tinta rosa no corpo da porta" + "Maçaneta metalica (foto 6), apresenta manchas e marcas de uso"
- Exemplo ERRADO: "Porta branca com maçaneta metalica (foto 6), estado bom" e so flagar "Maçaneta com manchas" nas Observacoes — isso OMITE o defeito da PORTA

REGRA CRITICA — ANTI-DUPLICACAO DE ITENS ENTRE SECOES:
- Cada item aparece em UMA UNICA secao do resumo, nunca em duas
- Portas e janelas vao em "Esquadrias" (NAO repita em "Itens e moveis")
- Luminarias, interruptores, tomadas, pontos de luz vao em "Instalacoes" (NAO repita em "Itens e moveis")
- Bancadas, cubas, espelhos, boxes, vasos sanitarios, chuveiros, torneiras vao em "Itens e moveis"
- Se voce ja descreveu a porta em "Esquadrias", NAO escreva outra linha sobre a porta em "Itens e moveis"

REGRA CRITICA — INSPECAO OBRIGATORIA DE SUJEIRA EM SUPERFICIES TRANSLUCIDAS E METALICAS:
- Antes de classificar "estado bom" para VIDRO (janela, box, espelho, vidro de eletrodomestico), CAIXILHO METALICO, RALO, TORNEIRA ou AZULEJO: examine a foto buscando sujeira, manchas, respingos, poeira, oxidacao ou residuos
- Se houver marcas visiveis (mesmo que discretas), reporte como "apresenta sujidade/manchas/marcas" — NAO classifique como "estado bom"
- Vidros sujos, caixilhos com poeira/manchas, espelhos com respingos SAO defeitos e DEVEM ser reportados

REGRA CRITICA — INVENTARIO COMPLETO OBRIGATORIO:
- Liste TODOS os itens visiveis nas fotos, sem filtrar por "importancia", "permanencia", "tamanho" ou "fixacao"
- Inclua OBRIGATORIAMENTE (varredura completa por foto):
  * Moveis fixos: cama, sofa, mesa, cadeira, guarda-roupa, rack, armario, comoda, estante, prateleira, bancada, criado-mudo
  * Eletrodomesticos: TV, geladeira, fogao, cooktop, forno, micro-ondas, coifa, lava-loucas, lava-roupas, secadora, ar-condicionado, aquecedor, VENTILADOR (de teto, pedestal, mesa, coluna ou parede)
  * Eletronicos portateis: abajur, luminaria de mesa, radio, caixa de som, notebook, impressora, umidificador
  * Decoracao: quadros, espelhos decorativos, plantas, vasos, tapetes, almofadas, cortinas, persianas
  * Utensilios visiveis em cozinha/lavanderia: liquidificador, batedeira, cafeteira, torradeira, purificador, ferro de passar
  * Acessorios de banheiro: porta-toalhas, porta-papel, saboneteira, dispenser
- PROIBIDO omitir item visivel porque parece "pequeno", "portatil", "nao-fixo", "temporario" ou "decorativo"
- Se um item aparece claramente em QUALQUER foto do lote, ELE DEVE constar em "Itens e moveis" (ou na secao apropriada conforme anti-duplicacao)
- VENTILADOR especificamente: IA costuma esquecer ventilador em cima de racks, mesas, ou no canto do quarto. SEMPRE confira se ha ventilador visivel antes de concluir o inventario

REGRA CRITICA — ITENS OBRIGATORIOS AUSENTES (falta de componente esperado E defeito):
Componentes estruturalmente esperados que ESTAO AUSENTES devem ser reportados como defeito ou observacao — a ausencia e tao importante quanto a presenca de um defeito visivel.
Pares item/componente obrigatorio a verificar:
- VASO SANITARIO — deve ter assento e tampa instalados. Se o vaso aparece apenas com o aro/bacia exposto, reporte: "Vaso sanitario sem assento nem tampa (foto N)"
- PIA/CUBA — deve ter torneira instalada. Se a pia aparece sem torneira, reporte: "Pia sem torneira instalada (foto N)"
- BOX DE BANHEIRO — deve ter porta ou cortina. Se o box aparece sem porta, reporte
- LUMINARIA (plafon, arandela, spot, pendente) — deve ter lampada e/ou globo/difusor. Se aparece apenas o bocal/fiacao exposta, reporte: "Ponto de luz sem lampada" ou "Luminaria sem globo/difusor"
- TOMADA e INTERRUPTOR — devem ter espelho/placa frontal. Se aparecem com caixa aberta/fiacao exposta, reporte
- PORTA — deve ter macaneta e fechadura visiveis. Se a porta aparece sem macaneta ou com ferragem faltando, reporte
- ARMARIO/GAVETA — deve ter puxador e porta. Se aparece com porta removida, puxador faltando, reporte
- JANELA — deve ter vidro ou vidraca. Se aparece com vidro quebrado/ausente, reporte
- CHUVEIRO — deve ter crivo/difusor (a parte furada que distribui a agua). Se aparece apenas o cano/registro sem o cabecote, reporte
Esta regra NAO te obriga a reportar componentes que voce simplesmente nao consegue ver na foto (ex: macaneta de porta que esta pro outro lado) — e OBRIGADO a reportar quando a AUSENCIA e claramente visivel na foto (ex: vaso sem assento, porta sem macaneta, tomada sem espelho).

REGRA CRITICA — NAO CONFUNDIR ELEMENTO ARQUITETONICO COM ELETRODOMESTICO/MOVEL:
Antes de afirmar que um painel vertical grande e "geladeira", "freezer" ou qualquer eletrodomestico grande, CONFIRME visualmente que e um ITEM INDEPENDENTE da estrutura do imovel. Painel vertical pode ser porta de correr, divisoria, armario embutido ou box arquitetonico — e NAO um eletrodomestico.
Protocolo obrigatorio de 4 perguntas antes de afirmar "geladeira/freezer/eletrodomestico":
1. E um corpo INDEPENDENTE apoiado no piso (nao integrado a parede/estrutura)? Geladeira sim; porta/divisoria nao.
2. Tem LOGO da marca visivel (Brastemp, Consul, Electrolux, Samsung, LG, Panasonic, Continental, Midea, etc.)? Geladeira moderna SEMPRE tem logo visivel. Porta/divisoria NAO tem logo de marca.
3. Altura vai do piso ate muito proximo do teto (ou ate o teto)? Geladeira normalmente NAO vai ate o teto (tem folga acima). Porta de correr e divisoria arquitetonica GERALMENTE vao do piso ao teto.
4. Superficie lisa brilhante (inox escovado, esmalte branco liso, vidro refrigerador)? Ou superficie FOSCA/TEXTURIZADA/LEITOSA? Geladeira tem superficie LISA. Porta/divisoria com painel fosco/texturizado NAO e geladeira.
Se NAO consegue responder SIM com certeza a pelo menos 3 dessas 4 perguntas, NAO AFIRME "geladeira". Use descricoes alternativas seguras:
- "Painel de correr com superficie fosca/texturizada fechando vao de passagem"
- "Divisoria de vao com painel texturizado e caixilho metalico"
- "Porta de correr com painel opaco e puxador vertical metalico"
- "Painel vertical de material nao determinado com precisao fechando vao"
Erro comum a EVITAR: afirmar "geladeira" para qualquer painel alto que apareca em cozinha. Porta de area de servico, porta de despensa, porta de passagem para outro comodo sao frequentemente confundidas com geladeira quando tem painel fosco e puxador vertical.
Consequencia dessa confusao alem do erro principal: a IA tende a transferir adjetivos errados para itens proximos (ex: "armarios com portas de correr" quando os armarios tem portas de abrir) — evite contaminacao cruzada.

REGRA CRITICA — ANTI-INVENCAO DE ABERTURAS ARQUITETONICAS (PORTA/JANELA/PASSAGEM):
Uma porta, janela ou passagem SO existe na foto quando voce VE CLARAMENTE pelo menos 2 dos 4 indicadores abaixo:
- CAIXILHO/BATENTE/MOLDURA retangular definindo uma abertura no plano da parede
- MATERIAL DIFERENTE do plano da parede (madeira, vidro, metal, painel fosco, folha de porta)
- DOBRADICAS, PUXADOR, FECHADURA, MACANETA, TRILHO ou FERRAGEM visivel
- VAO ABERTO mostrando outro comodo/area alem da parede
NAO e porta/janela/passagem:
- Parede mais clara ao fundo ou regiao de parede com iluminacao diferente
- Extremidade do enquadramento (onde a foto simplesmente corta)
- Sombra ou canto escuro que sugere profundidade sem abertura definida
- Area da parede com menos detalhe ou mais desfocada
- Azulejo/revestimento uniforme sem interrupcao estrutural
Na duvida: NAO inclua "porta branca ao fundo" nem "janela visivel" nem "passagem" em "Esquadrias". O custo de omitir uma porta real e menor que o custo de inventar uma porta inexistente.

REGRA CRITICA — PROIBIDO JULGAMENTO ESTETICO OU SUBJETIVO:
- NAO escreva frases de valor sobre impacto visual ou estetica, como: "compromete a apresentacao", "prejudica a aparencia", "afeta a estetica", "deixa o ambiente feio/ruim", "visualmente desagradavel", "prejudica visualmente"
- Estado geral e Observacoes devem se limitar a FATOS: o que e visivel, onde esta, e classificacao objetiva (Bom / Regular / Com avaria)
- Exemplo CORRETO: "Estado geral: Regular — cooktop e forno apresentam sujidade visivel (fotos 7, 8)"
- Exemplo ERRADO: "...sujidade que compromete a apresentacao do ambiente"
- AMPLIACAO — PROIBIDO RECOMENDACOES: NAO escreva sugestoes ou conselhos sobre manutencao/cuidado futuro, como: "pode requerer manutencao", "precisa de cuidado", "recomenda-se aparar", "necessita pintura", "seria bom limpar", "convem verificar", "aconselha-se fazer", "deve ser revisado". Observacoes sao FATOS do que e visivel AGORA, nao sugestoes do que fazer depois
- Exemplo ERRADO: "Vegetacao proxima a edificacao pode requerer manutencao periodica" (e recomendacao)
- Exemplo CORRETO: OMITA completamente essa linha; se for relevante, escreva apenas o FATO: "Vegetacao densa proxima a edificacao (foto N)"

REGRA CRITICA — DISTANCIA E NIVEL DE DETALHE:
- Se um elemento aparece DISTANTE na foto (ocupa menos de ~30% do frame, esta visivelmente no fundo/paisagem, ou os detalhes nao sao nitidamente discernidos), descreva APENAS: presenca + forma geral + cor geral
- PROIBIDO afirmar manchas, desgaste, irregularidades, rachaduras, textura especifica, tipo de acabamento, tipo de material em elementos distantes
- PROIBIDO classificar estado (bom/regular/avaria) de elementos distantes — use "visivel ao fundo" ou descricao neutra sem classificacao
- Regra simples: se voce precisaria chegar mais perto para CONFIRMAR o que esta dizendo, NAO diga
- Exemplos:
  * Foto ampla de chacara com casa a ~30m no fundo: CORRETO "Casa visivel ao fundo com paredes em tom rosado/terracota e parede lateral em pedra aparente (foto 1)" — NAO afirme manchas, desgaste ou estado
  * Foto de quintal mostrando muro no fundo: CORRETO "Muro em cor clara ao fundo (foto N)" — NAO classifique estado do muro
  * Foto ampla onde a porta aparece distante: CORRETO "Porta de entrada escura visivel ao fundo (foto N)" sem afirmar estado
- Essa regra e distinta de FOCO DA FOTO (que fala de close de item): aqui o foco e em fotos AMPLAS onde um elemento aparece como contexto/paisagem distante

REGRA CRITICA — DETECCAO DE DEFEITOS POR COMPARACAO ENTRE ELEMENTOS SIMILARES:
- Quando houver MULTIPLOS elementos do MESMO tipo na foto (luminarias iguais, azulejos, ripas de piso, rodape continuo, interruptores, tomadas, portas de armario, lampadas de um trilho), COMPARE-OS entre si
- Se um elemento esta DIFERENTE dos outros similares, isso e sinal de DEFEITO POTENCIAL — NAO interprete como "modelo diferente" ou "caracteristica do produto"
- Casos tipicos que indicam DEFEITO:
  * Luminaria APAGADA enquanto outras iguais estao ACESAS -> lampada QUEIMADA (reporte como defeito)
  * Azulejo com cor ou tom diferente no meio de fileira identica -> azulejo manchado, substituido mal, ou com infiltracao
  * Ripa de piso ou tabua desalinhada vs as outras adjacentes -> levantamento ou defeito de instalacao
  * Interruptor/tomada com cor ou estado diferente dos outros iguais -> queimado, sujo ou com problema
  * Porta de armario desalinhada vs as outras portas do mesmo conjunto -> dobradica solta ou mal instalada
- Exemplo ERRADO (falha real da IA): "Luminaria embutida sem moldura visivel" quando na verdade era uma luminaria igual as outras do teto mas APAGADA/QUEIMADA
- Exemplo CORRETO: "Quatro luminarias embutidas acesas + uma luminaria APAGADA no canto superior esquerdo (foto 1), sugerindo lampada queimada ou pontual desligado"
- Regra de bolso: antes de descrever um elemento como tendo caracteristica diferente, pergunte-se "os outros elementos iguais estao assim tambem?" Se NAO estao, provavelmente e defeito

REGRA CRITICA — NUNCA DESCREVA POR REFLEXO:
- PROIBIDO descrever piso, paredes, teto, ambiente ou qualquer elemento com base em REFLEXOS visiveis em superficies espelhadas ou polidas (porta de vidro ou inox de eletrodomesticos, espelhos, vidros, bancadas polidas, telas de TV, superficies metalicas)
- Reflexo NAO e evidencia valida: a imagem esta distorcida, invertida e parcial
- So descreva um elemento quando ele estiver DIRETAMENTE enquadrado na foto, nao quando aparecer como reflexo em outro objeto
- Exemplo ERRADO: usar o reflexo do piso no vidro da porta do micro-ondas para descrever "Piso: ceramica clara"
- Exemplo CORRETO: ignorar o reflexo e descrever APENAS o item principal da foto (ex: o micro-ondas)
"""

def analisar_foto(imagem_base64: str, nome_ambiente: str, mime_type: str = "image/jpeg") -> dict:
    """
    Analisa uma foto de vistoria e retorna descricao tecnica completa.

    Retorna:
    {
        "item": str,
        "ambiente_detectado": str,
        "estado": str,
        "cor": str,
        "material": str,
        "descricao": str,
        "observacao": str,
        "novo_ambiente": bool,
        "success": bool
    }
    """

    prompt = f"""Analise esta foto de vistoria imobiliaria.
Ambiente informado pelo vistoriador: {nome_ambiente}

Retorne APENAS este JSON (sem markdown, sem texto fora do JSON):
{{
  "item": "nome tecnico do item principal fotografado (ex: Parede norte, Piso ceramico, Guarda-roupa, Janela basculante)",
  "ambiente_detectado": "nome do ambiente que voce identifica visualmente na foto",
  "estado": "Bom ou Regular ou Com avaria",
  "cor": "cor principal do item (seja especifico: branco gelo, carvalho medio, cinza claro, etc)",
  "material": "material identificado (tinta acrilica, ceramica 60x60cm, MDF, madeira macica, etc)",
  "descricao": "descricao tecnica detalhada em 4 a 6 linhas. Inclua: tipo do item, cor exata, material, dimensoes estimadas se visiveis, estado de conservacao detalhado, presenca de avarias com localizacao e extensao estimada",
  "observacao": "descricao da anomalia se houver (vazio se nao houver problema)",
  "novo_ambiente": false
}}

IMPORTANTE:
- Se o ambiente visivel na foto for DIFERENTE de '{nome_ambiente}', coloque o nome correto em 'ambiente_detectado' e defina 'novo_ambiente' como true
- Se for o mesmo ambiente, repita '{nome_ambiente}' em 'ambiente_detectado' e mantenha 'novo_ambiente' como false
- Estado 'Com avaria' apenas se houver dano visivel real: rachadura, descascamento, infiltracao, quebra, mofo, etc"""

    for tentativa in range(3):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=1000,
                temperature=0.2,
                system=SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": imagem_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }]
            )

            texto = response.content[0].text.strip()
            texto = re.sub(r'```json\s*', '', texto)
            texto = re.sub(r'```\s*', '', texto)
            texto = texto.strip()

            dados = json.loads(texto, strict=False)
            dados['success'] = True

            # Normalizar estado
            estado = dados.get('estado', 'Bom')
            if 'avaria' in estado.lower() or 'mau' in estado.lower():
                dados['estado'] = 'Com avaria'
            elif 'regular' in estado.lower():
                dados['estado'] = 'Regular'
            else:
                dados['estado'] = 'Bom'

            return dados

        except json.JSONDecodeError:
            # Tentar extrair JSON do texto
            match = re.search(r'\{[\s\S]*\}', texto)
            if match:
                try:
                    dados = json.loads(match.group())
                    dados['success'] = True
                    return dados
                except:
                    pass
        except Exception as e:
            if tentativa < 2:
                time.sleep(2 ** tentativa)
            else:
                return {
                    "item": "Item nao identificado",
                    "ambiente_detectado": nome_ambiente,
                    "estado": "Bom",
                    "cor": "",
                    "material": "",
                    "descricao": f"Erro ao analisar imagem: {str(e)}",
                    "observacao": "",
                    "novo_ambiente": False,
                    "success": False
                }

    return {
        "item": "Item nao identificado",
        "ambiente_detectado": nome_ambiente,
        "estado": "Bom",
        "cor": "",
        "material": "",
        "descricao": "Nao foi possivel analisar a imagem apos 3 tentativas.",
        "observacao": "",
        "novo_ambiente": False,
        "success": False
    }


def consolidar_ambiente(nome_ambiente: str, descricoes: list) -> dict:
    """
    Consolida todas as descricoes de fotos de um ambiente em sintese estruturada.
    """
    if not descricoes:
        return {"resumo": "", "success": False}

    itens_texto = ""
    for i, d in enumerate(descricoes, 1):
        itens_texto += f"Foto {i} -- {d.get('item', 'Item')}: {d.get('descricao', '')}\n"

    prompt = f"""Voce e um perito em vistorias imobiliarias. Com base nas descricoes das fotos abaixo do ambiente '{nome_ambiente}', gere uma SINTESE ESTRUTURADA profissional.

DESCRICOES DAS FOTOS:
{itens_texto}

INSTRUCOES:
- Organize a sintese por elementos construtivos identificados nas fotos
- Para cada elemento mencione: material, cor e estado de conservacao
- Se houver avaria, descreva com precisao e destaque claramente
- Use linguagem tecnica de laudo pericial
- Seja objetivo e preciso
- Conclua com o estado geral do ambiente

Retorne APENAS este JSON sem markdown:
{{
  "resumo": "SINTESE:\n\nPiso: [material, cor, estado]\n\nParedes: [material, cor, estado, avarias se houver]\n\nTeto: [material, cor, estado]\n\nEsquadrias: [portas e janelas, estado]\n\nObservacoes: [itens adicionais identificados]\n\nEstado geral: [Bom / Regular / Com avaria] -- [justificativa resumida]"
}}"""

    for tentativa in range(3):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=800,
                temperature=0.2,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )
            texto = response.content[0].text.strip()
            texto = re.sub(r'```json\s*', '', texto)
            texto = re.sub(r'```\s*', '', texto)
            texto = texto.strip()
            dados = json.loads(texto, strict=False)
            dados['success'] = True
            return dados
        except Exception as e:
            if tentativa < 2:
                time.sleep(2 ** tentativa)

    return {"resumo": "", "success": False}


def analisar_foto_simples(imagem_base64: str, nome_ambiente: str = "Ambiente", mime_type: str = "image/jpeg") -> dict:
    """
    Modo legado -- compatibilidade com codigo anterior.
    Chama analisar_foto e normaliza para formato antigo.
    """
    resultado = analisar_foto(imagem_base64, nome_ambiente, mime_type)

    return {
        "description": resultado.get("descricao", ""),
        "estado": resultado.get("estado", "Bom"),
        "descricao_geral": resultado.get("descricao", ""),
        "item": resultado.get("item", ""),
        "ambiente_detectado": resultado.get("ambiente_detectado", nome_ambiente),
        "cor": resultado.get("cor", ""),
        "material": resultado.get("material", ""),
        "observacao": resultado.get("observacao", ""),
        "novo_ambiente": resultado.get("novo_ambiente", False),
        "itens": [
            {
                "nome": resultado.get("item", "Item"),
                "estado": resultado.get("estado", "Bom"),
                "descricao": resultado.get("descricao", "")
            }
        ],
        "observacoes": [resultado.get("observacao")] if resultado.get("observacao") else [],
        "condition": resultado.get("estado", "Bom"),
        "success": resultado.get("success", False)
    }


# Funcao principal chamada pelo server.py
def analisar_imagem(imagem_base64: str, ambiente: str = "Ambiente", modo: str = "completo", mime_type: str = "image/jpeg") -> dict:
    """
    Ponto de entrada principal.
    modo: 'completo' (novo) | 'simples' (legado)
    """
    if modo == 'simples':
        return analisar_foto_simples(imagem_base64, ambiente, mime_type)
    else:
        return analisar_foto(imagem_base64, ambiente, mime_type)

def analisar_batch(imagens: list, nome_ambiente: str, tipo_vistoria: str = "entrada") -> dict:
    """
    Analisa um lote de fotos do mesmo ambiente em uma unica chamada.
    """
    last_error = ""
    if not imagens:
        return {"resumo": "", "estado_geral": "Bom", "success": False}

    LOTE_MAX = 20
    lotes = [imagens[i:i+LOTE_MAX] for i in range(0, len(imagens), LOTE_MAX)]
    resumos = []
    all_extras = []

    for lote in lotes:
        content = []
        for idx_foto, img in enumerate(lote, 1):
            content.append({"type": "text", "text": f"--- FOTO {idx_foto} ---"})
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": img.get("mime_type", "image/jpeg"),
                    "data": img["base64"]
                }
            })

        prompt = f"""Voce recebeu {len(lote)} foto(s) do ambiente '{nome_ambiente}'.
Tipo de vistoria: {tipo_vistoria}
Cada foto esta numerada (FOTO 1, FOTO 2, etc).

PASSO 1 — CLASSIFICAR CADA FOTO (REGRA FUNDAMENTAL):
Para cada foto, primeiro determine o TIPO:

a) FOTO AMPLA (sem zoom) — mostra visao geral do ambiente, distancia maior
   - Faca descricao SUPERFICIAL: cores, materiais, itens presentes, layout geral
   - NAO aponte defeitos ou avarias em fotos amplas — a distancia nao permite precisao
   - NAO invente problemas que nao sao claramente visiveis
   - Apenas descreva o que ve de forma geral: "parede branca", "piso ceramico claro", "luminaria no teto"

b) FOTO EM FOCO/ZOOM — focada em elemento especifico (close-up)
   - Esta foto foi tirada INTENCIONALMENTE para mostrar algo especifico
   - Faca ANALISE CLINICA PONTUAL: marca, tipo, estado de conservacao, avarias, manchas, trincas
   - Se mostra um item (fechadura, torneira, chuveiro) — descreva marca/tipo/estado com precisao
   - Se mostra avaria/defeito — descreva o defeito com precisao maxima
   - Se mostra item sem defeito — descreva o item e confirme "sem avaria identificada"

REGRAS CRITICAS DE DESCRICAO:
- NUNCA afirme que algo NAO esta instalado (ex: "chuveiro nao instalado") — se nao ve com certeza, NAO mencione
- NUNCA invente defeitos que nao sao CLARAMENTE visiveis na foto
- Se um item aparece na foto (ex: chuveiro na parede), descreva como PRESENTE/INSTALADO
- So aponte avaria quando for INEQUIVOCAMENTE visivel
- Em fotos amplas, use linguagem neutra: "estado aparentemente bom" ou apenas descreva o que ve
- Em fotos em zoom/foco, seja preciso e clinico: descreva exatamente o que o foco revela
- Se a foto mostra item sem problema evidente, diga "sem avaria identificada" — NAO force defeitos

PASSO 2 — EXAMINAR DEFEITOS (SOMENTE SE CLARAMENTE VISIVEIS):
Para cada foto, verifique APENAS o que e claramente visivel:
- Furos ou buracos no piso, paredes ou teto?
- Manchas escuras, mofo, bolor, umidade?
- Fissuras, trincas ou rachaduras?
- Fios ou fiacao aparente/exposta?
- Descolamento, descascamento ou desgaste?
- Rodapes soltos ou afastados da parede?
- Rejuntes falhos, escurecidos ou com mofo?
- Pontos escuros dispersos no piso (sujidade grave ou infestacao)?
- Oxidacao, ferrugem ou deterioracao em metais?

ANTES de registrar qualquer mancha/sujidade/infiltracao/desgaste, responda mentalmente 4 perguntas:
1. A suposta "mancha" tem forma compativel com luz natural entrando por janela ou luminaria, com gradiente suave? -> e SOMBRA, NAO defeito
2. A suposta "mancha" se repete ritmicamente pelo piso/parede acompanhando o desenho do material? -> e PADRAO/VEIO/TEXTURA do material, NAO defeito
3. A cor destoante esta restrita a linhas entre pecas? -> e REJUNTE, NAO defeito
4. Ha brilho/reflexo numa superficie polida? -> e REFLEXO de luz, NAO defeito
So prossiga com o defeito se nenhuma das 4 hipoteses acima se aplica.

IMPORTANTE: So reporte um defeito se voce tem CERTEZA VISUAL. Em fotos amplas, nao force deteccao de defeitos.

PASSO 3 â REGRAS DE DESCRICAO:
- SO descreva teto se aparecer claramente em alguma foto â se nao aparecer, OMITA a secao Teto
- SO descreva piso se aparecer claramente em alguma foto â se nao aparecer, OMITA a secao Piso
- Pedra com veios visiveis = "pedra natural" ou "marmore" â NUNCA "granito" sem certeza
- NUNCA mencione medidas ou dimensoes
- Material apenas com certeza visual absoluta
- Ignore elementos ao fundo atraves de portas/aberturas
- {"IGNORE objetos pessoais: tapetes, vasos, produtos de higiene, roupas, itens do morador" if tipo_vistoria in ["entrada", "saida"] else "INVENTARIE todos os itens presentes incluindo decoracao, utensilios e equipamentos"}

PASSO 4 â DETECTAR AMBIENTES DIFERENTES (OBRIGATORIO):
ANTES de sintetizar, verifique: as fotos correspondem ao ambiente '{nome_ambiente}'?

SINAIS DE AMBIENTE ERRADO:
- Vaso sanitario, box, chuveiro, ralo = BANHEIRO (nao dormitorio, nao sala)
- Fogao, pia de cozinha, coifa = COZINHA (nao sala, nao dormitorio)
- Cama, guarda-roupa, criado-mudo = DORMITORIO (nao sala, nao cozinha)
- Tanque, maquina de lavar = AREA DE SERVICO
- Portao, vaga de carro, piso cimentado largo, portao automatico = GARAGEM (nao sala)
- Corredor estreito, passagem entre comodos, hall = CORREDOR (nao sala, nao dormitorio)
- Jardim, quintal, area descoberta, muro externo, churrasqueira, piscina = AREA EXTERNA
- Varanda, sacada, area coberta com vista externa = VARANDA
- Fachada do imovel, frente da casa, porta de entrada vista de fora, visao geral do exterior = FACHADA (nao garagem, mesmo se portao visivel)

IMPORTANTE: Se a foto mostra um espaco amplo com piso cimentado ou sem acabamento refinado,
com portao ou acesso de veiculos, E GARAGEM â nao Sala.
Se a foto mostra area descoberta ou semicoberta com muros, E AREA EXTERNA â nao Sala.
Se a foto mostra espaco estreito de passagem sem moveis, E CORREDOR â nao Sala.
Se a foto mostra a FRENTE/EXTERIOR do imovel com foco na fachada, E FACHADA — nao Garagem, mesmo que o portao de garagem apareca na imagem.

Se as fotos mostram um ambiente DIFERENTE de '{nome_ambiente}':
- Liste TODAS as fotos que pertencem ao outro ambiente em "ambientes_extras"
- Use o nome correto (ex: 'Banheiro', 'Cozinha', 'Dormitorio', 'Garagem', 'Corredor', 'Area externa', 'Fachada')
- Se TODAS as fotos sao de outro ambiente, liste TODAS as fotos em ambientes_extras

ISTO E OBRIGATORIO. Nao descreva fotos de banheiro como se fossem dormitorio, nem fotos de garagem como se fossem sala.

PASSO 5 â SINTETIZAR:
Compile tudo em descricao unica sem omitir nenhum defeito.
Para CADA elemento ou defeito, inclua entre parenteses o numero da foto: (foto N)
Prioridade: fotos de avaria > fotos de item > fotos amplas.

REGRA CRITICA DE SINTESE — ELEMENTOS CONSTRUTIVOS (Piso, Paredes, Teto, Rodapes, Bancada):
- So emita linhas "Piso:", "Paredes:", "Teto:", "Rodapes:", "Bancada:" se PELO MENOS UMA foto do lote for AMPLA e esse elemento estiver claramente enquadrado e em foco
- PROIBIDO inferir estado de parede/piso/teto a partir do FUNDO INCIDENTAL de fotos close de itens (ex: close de liquidificador dentro de armario NAO permite descrever "paredes brancas")
- Se o lote so contem fotos close de itens, a sintese deve descrever APENAS os itens, OMITINDO completamente as linhas de Piso/Paredes/Teto
- Quando omitir uma linha, simplesmente NAO a inclua no resumo — NAO escreva "nao visivel" ou similar

CHECKLIST FINAL OBRIGATORIO antes de retornar o JSON (auditoria linha a linha):
Para CADA linha do resumo ("Piso:", "Paredes:", "Teto:", "Rodapes:", "Bancada:", "Moveis:", "Armarios:", etc.), responda mentalmente 2 perguntas:

Pergunta 1: Existe alguma foto onde esse elemento esta DIRETAMENTE enquadrado (foto AMPLA do ambiente ou foto com foco no proprio elemento), e NAO apenas visivel como fundo de um close de outro item?
-> Se NAO, REMOVA a linha inteira do resumo. NAO escreva "nao visivel" ou similar, simplesmente OMITA a linha.

Pergunta 2: A unica evidencia desse elemento e um REFLEXO visivel em superficie espelhada (vidro de micro-ondas, porta de forno, inox, espelho, bancada polida, tela de TV)?
-> Se SIM, REMOVA a linha inteira do resumo. Reflexo e PROIBIDO como evidencia.

Exemplo pratico: Foto 4 = close do micro-ondas com vidro espelhado que reflete piso e armarios. Se piso/armarios SO aparecem nesse reflexo, AUDITORIA FALHA -> OMITA "Piso:" e "Armarios:" do resumo, mesmo que a foto 4 "mostre" esses elementos via reflexo.

Se apos a auditoria o resumo ficar apenas com itens (eletrodomesticos, utensilios, moveis), isso esta CORRETO. NAO force uma linha de Piso/Paredes/Teto so para "preencher" a estrutura.

ETAPA FINAL OBRIGATORIA — VARREDURA DE INVENTARIO COMPLETO:
Antes de retornar o JSON, percorra CADA foto do lote (foto 1, foto 2, foto 3, ...) e faca uma varredura visual completa.

Pergunta 3: Para cada foto, existe algum item CLARAMENTE visivel (mesmo que pequeno, portatil ou no fundo) que NAO aparece na minha lista de "Itens e moveis"?
-> Itens frequentemente ESQUECIDOS por IA: VENTILADOR (pedestal/mesa/teto/parede), ar-condicionado split ou janela, aquecedor, abajur, luminaria de mesa, tapete, almofadas, cortinas, plantas, quadros, espelhos, criado-mudo, mesa lateral, caixa de som, umidificador.
-> Se SIM (ha item visivel nao listado), ACRESCENTE o item antes de retornar o JSON.
-> VENTILADOR especificamente: confira se ha algum ventilador (pedestal, mesa, teto, coluna ou parede) em qualquer foto e inclua OBRIGATORIAMENTE se houver. Ventilador e o item mais frequentemente esquecido em dormitorios.

EXEMPLO COMPLETO DE SAIDA CORRETA para um lote de 8 closes de eletrodomesticos em cozinha (SEM foto ampla do ambiente).
Campo "resumo" deve ser EXATAMENTE assim (nenhuma linha de Piso/Paredes/Teto):
---
SINTESE DO AMBIENTE:

Itens e moveis:
- Micro-ondas Philco prata e preto, display 17:01 (foto 1), estado bom
- Purificador Electrolux Acqua Pure (foto 2), estado bom
- Conjunto de tacas e copos de vidro com lapidacao (foto 3), estado bom
- Air fryer preto e prata (foto 4), estado bom
- Panela de pressao eletrica Wap (foto 5), estado bom
- Liquidificador Philco (foto 6), estado bom
- Forno eletrico Mueller Fratello (foto 7), apresenta sujidade no vidro da porta
- Cooktop Philco 5 bocas a gas (foto 8), apresenta sujidade na superficie

Observacoes:
- Forno eletrico com sujidade visivel no vidro da porta (foto 7)
- Cooktop com sujidade e residuos na superficie (foto 8)

Estado geral: Regular — forno e cooktop apresentam sujidade visivel (fotos 7, 8)
---
NOTE: este resumo CORRETO NAO tem linha "Piso:", NAO tem linha "Paredes:", NAO tem linha "Teto:". Nenhuma foto do lote enquadra diretamente esses elementos — reflexos em vidros/inox/espelhos de eletrodomesticos NAO contam como evidencia. Se o seu lote for parecido (so closes de itens), reproduza esse padrao.

Retorne APENAS este JSON sem markdown:
{{{{
  "resumo": "SINTESE DO AMBIENTE:\n\nItens e moveis:\n- [liste cada item/movel/eletrodomestico com (foto N) e estado]\n\n[SECAO OPCIONAL - ELEMENTOS CONSTRUTIVOS: inclua as linhas abaixo SOMENTE se houver foto AMPLA do ambiente enquadrando DIRETAMENTE o elemento. Reflexo em vidro/inox NAO conta. Se NAO houver foto ampla direta, OMITA cada linha por completo. NAO escreva 'nao visivel' ou similar]\n[Piso: revestimento, cor, estado (foto N)]\n[Paredes: acabamento, cor, estado (foto N)]\n[Teto: acabamento, cor, estado (foto N)]\n[Rodapes: material, cor, estado (foto N)]\n[Bancada: material, cor, estado (foto N)]\n[Esquadrias: portas e janelas visiveis, estado (foto N)]\n[Instalacoes: tomadas, interruptores, pontos de luz — fios aparentes DEVEM ser reportados (foto N)]\n\nObservacoes: [LISTA COMPLETA de defeitos factuais com (foto N)]\n\nEstado geral: [Bom / Regular / Com avaria] — [justificativa factual, sem julgamento estetico]",
  "estado_geral": "Bom ou Regular ou Com avaria",
  "ambientes_extras": [
    {{{{
      "nome": "Nome do ambiente detectado",
      "fotos": [1],
      "descricao": "Descricao do ambiente...",
      "estado": "Bom ou Regular ou Com avaria"
    }}}}
  ]
}}}}
Se TODAS as fotos pertencem ao ambiente "{nome_ambiente}", retorne "ambientes_extras": []"""

        content.append({"type": "text", "text": prompt})

        for tentativa in range(3):
            try:
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=4000,
                    temperature=0.2,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": content}]
                )
                texto = response.content[0].text.strip()
                texto = re.sub(r'```json\s*', '', texto)
                texto = re.sub(r'```\s*', '', texto)
                texto = texto.strip()
                dados = json.loads(texto, strict=False)
                resumos.append(dados.get("resumo", ""))
                extras = dados.get("ambientes_extras", [])
                if extras:
                    all_extras.extend(extras)
                break
            except Exception as e:
                last_error = str(e)
                print(f"[analisar_batch] Tentativa {tentativa+1}/3 falhou: {e}")
                if tentativa < 2:
                    time.sleep(2 ** tentativa)

    resumo_final = "\n\n".join([r for r in resumos if r])
    estado = "Bom"
    if "com avaria" in resumo_final.lower() or "avaria" in resumo_final.lower():
        estado = "Com avaria"
    elif "regular" in resumo_final.lower():
        estado = "Regular"

    result = {"resumo": resumo_final, "estado_geral": estado, "success": bool(resumo_final), "ambientes_extras": all_extras}
    if not resumo_final and last_error:
        result["error"] = last_error
    return result


def analyze_batch(images: list, environment_name: str, tipo_vistoria: str = "entrada") -> dict:
    return analisar_batch(images, environment_name, tipo_vistoria)


# Aliases em ingles para compatibilidade com server.py
def analyze_photo(image_base64: str, environment: str = "Ambiente", mime_type: str = "image/jpeg") -> dict:
    return analisar_foto(image_base64, environment, mime_type)

def analyze_photos(images_base64: list, environment: str = "Ambiente", mime_type: str = "image/jpeg") -> list:
    return [analisar_foto(img, environment, mime_type) for img in images_base64]

def consolidate_environment(environment_name: str, descriptions: list) -> dict:
    return consolidar_ambiente(environment_name, descriptions)

def analyze_image(image_base64: str, environment: str = "Ambiente", mode: str = "completo", mime_type: str = "image/jpeg") -> dict:
    return analisar_imagem(image_base64, environment, mode, mime_type)
