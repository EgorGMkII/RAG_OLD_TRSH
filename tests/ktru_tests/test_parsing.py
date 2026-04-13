from __future__ import annotations

from services.procurement_reference_registry import ProcurementReferenceRegistry


def test_parse_ktru_common_info_html_minimal(
    registry: ProcurementReferenceRegistry,
) -> None:
    html = """
    <html>
      <body>
        <div class="cardMainInfo__section">
          <div class="cardMainInfo__content">Зерно ржи</div>
        </div>

        <div class="blockInfo__section section">
          <div class="section__title">Код по ОКПД2</div>
          <div class="section__info">01.11.32.000: Культуры зерновые прочие</div>
        </div>

        <div class="blockInfo__section section">
          <div class="section__title">Единицы измерения (количество товара, объем работы, услуги по ОКЕИ)</div>
          <div class="section__info">Тонна;^метрическая тонна (1000 кг)</div>
        </div>

        <div class="blockInfo__section section">
          <div class="section__title">Дата начала обязательного применения позиции каталога</div>
          <div class="section__info">01.01.2024</div>
        </div>

        <div class="sectionMainInfo__body">
          <div class="cardMainInfo__title">Цвет: коричневый; Влажность: не более 14%</div>
        </div>
      </body>
    </html>
    """

    payload = registry.parse_ktru_common_info_html(
        html=html,
        ktru_code="01.11.32.000-00000002",
    )

    assert payload["ktru_code"] == "01.11.32.000-00000002"
    assert payload["name"] == "Зерно ржи"
    assert payload["okpd2_code"] == "01.11.32.000"
    assert payload["okpd2_name"] == "Культуры зерновые прочие"
    assert payload["unit"] == "Тонна;^метрическая тонна (1000 кг)"
    assert payload["application_date_start"] == "01.01.2024"
    assert payload["summary_characteristics"] == {
        "Цвет": "коричневый",
        "Влажность": "не более 14%",
    }
    assert payload["short_description"] == [
        "Единица измерения: Тонна;^метрическая тонна (1000 кг)",
        "Цвет: коричневый",
        "Влажность: не более 14%",
    ]


def test_extract_main_name_fallback_from_section_title(
    registry: ProcurementReferenceRegistry,
) -> None:
    html = """
    <html>
      <body>
        <div class="blockInfo__section section">
          <div class="section__title">Наименование товара, работы, услуги</div>
          <div class="section__info">Зерно ржи</div>
        </div>
      </body>
    </html>
    """

    payload = registry.parse_ktru_common_info_html(
        html=html,
        ktru_code="01.11.32.000-00000002",
    )

    assert payload["name"] == "Зерно ржи"