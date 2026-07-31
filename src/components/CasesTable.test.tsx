/* eslint-disable @typescript-eslint/no-non-null-assertion */
import { describe, it, expect } from 'vitest';
import { render } from 'vitest-browser-react';
import {
  CasesTable,
  NOUN_CASES,
  ADJ_CASES,
  NOUN_COLUMNS,
  SIMPLE_NOUN_COLUMNS,
  ADJ_COLUMNS,
} from './CasesTable';
import { VerbTable } from './VerbTable';
import type { DictionaryForms } from '../types/words';

function getCaseCells(
  container: HTMLElement,
  caseLabel: string,
): HTMLTableCellElement[] {
  const ths =
    container.querySelectorAll<HTMLTableCellElement>('th[scope="row"]');
  for (const th of ths) {
    if (th.textContent.trim() === caseLabel) {
      const tr = th.closest('tr');
      return tr
        ? Array.from(tr.querySelectorAll<HTMLTableCellElement>('td'))
        : [];
    }
  }
  return [];
}

describe('Noun cell merging (rowSpan across cases)', () => {
  it('merges nom and acc cells when they have the same value (singular)', async () => {
    const forms: DictionaryForms = {
      'nom ns': 'будинок',
      'acc ns': 'будинок',
      'gen ns': 'будинку',
      'dat ns': 'будинку',
      'ins ns': 'будинком',
      'loc ns': 'будинку',
      'voc ns': 'будинку',
      'nom np': 'будинки',
      'acc np': 'будинки',
      'gen np': 'будинків',
      'dat np': 'будинкам',
      'ins np': 'будинками',
      'loc np': 'будинках',
      'voc np': 'будинки',
    };
    const screen = await render(
      <CasesTable
        forms={forms}
        query=""
        cases={NOUN_CASES}
        columns={NOUN_COLUMNS}
      />,
    );

    await expect
      .element(screen.getByRole('rowheader', { name: 'Nom.' }))
      .toBeVisible();

    const nomCells = getCaseCells(screen.container, 'Nom.');
    expect(nomCells[0].rowSpan).toBe(2);

    const accCells = getCaseCells(screen.container, 'Acc.');
    const accHasSingCell = accCells.some((c) => c.textContent === 'будинок');
    expect(accHasSingCell).toBe(false);
  });

  it('does NOT merge nom and acc when values differ', async () => {
    const forms: DictionaryForms = {
      'nom ns': 'кіт',
      'acc ns': 'кота',
      'gen ns': 'кота',
      'dat ns': 'коту',
      'ins ns': 'котом',
      'loc ns': 'коті',
      'voc ns': 'коте',
      'nom np': 'коти',
      'acc np': 'котів',
      'gen np': 'котів',
      'dat np': 'котам',
      'ins np': 'котами',
      'loc np': 'котах',
      'voc np': 'коти',
    };
    const screen = await render(
      <CasesTable
        forms={forms}
        query=""
        cases={NOUN_CASES}
        columns={NOUN_COLUMNS}
      />,
    );

    await expect
      .element(screen.getByRole('rowheader', { name: 'Nom.' }))
      .toBeVisible();
    await expect
      .element(screen.getByRole('rowheader', { name: 'Acc.' }))
      .toBeVisible();

    const nomCells = getCaseCells(screen.container, 'Nom.');
    const accCells = getCaseCells(screen.container, 'Acc.');

    expect(nomCells[0].rowSpan).toBe(1);
    expect(accCells.length).toBeGreaterThanOrEqual(1);
    expect(accCells[0].textContent).toBe('кота');
  });

  it('merges multiple consecutive cases with the same value', async () => {
    const forms: DictionaryForms = {
      'nom ns': 'слово',
      'acc ns': 'слово',
      'gen ns': 'слова',
      'dat ns': 'слову',
      'ins ns': 'словом',
      'loc ns': 'слові',
      'voc ns': 'слово',
      'nom np': 'слова',
      'acc np': 'слова',
      'gen np': 'слів',
      'dat np': 'словам',
      'ins np': 'словами',
      'loc np': 'словах',
      'voc np': 'слова',
    };
    const screen = await render(
      <CasesTable
        forms={forms}
        query=""
        cases={NOUN_CASES}
        columns={NOUN_COLUMNS}
      />,
    );

    await expect
      .element(screen.getByRole('rowheader', { name: 'Nom.' }))
      .toBeVisible();

    const nomCells = getCaseCells(screen.container, 'Nom.');
    expect(nomCells[0].rowSpan).toBe(2);
  });

  it('merges gen, dat, loc when they share the same value', async () => {
    const forms: DictionaryForms = {
      'nom ns': 'будинок',
      'acc ns': 'будинок',
      'gen ns': 'будинку',
      'dat ns': 'будинку',
      'ins ns': 'будинком',
      'loc ns': 'будинку',
      'voc ns': 'будинку',
      'nom np': 'будинки',
      'acc np': 'будинки',
      'gen np': 'будинків',
      'dat np': 'будинкам',
      'ins np': 'будинками',
      'loc np': 'будинках',
      'voc np': 'будинки',
    };
    const screen = await render(
      <CasesTable
        forms={forms}
        query=""
        cases={NOUN_CASES}
        columns={NOUN_COLUMNS}
      />,
    );

    await expect
      .element(screen.getByRole('rowheader', { name: 'Gen.' }))
      .toBeVisible();

    const genCells = getCaseCells(screen.container, 'Gen.');
    expect(genCells[0].textContent).toBe('будинку');
    expect(genCells[0].rowSpan).toBeGreaterThan(1);
  });

  it('works for simple nouns (single column)', async () => {
    const forms: DictionaryForms = {
      'nom n': 'молоко',
      'acc n': 'молоко',
      'gen n': 'молока',
      'dat n': 'молоку',
      'ins n': 'молоком',
      'loc n': 'молоці',
      'voc n': 'молоко',
    };
    const screen = await render(
      <CasesTable
        forms={forms}
        query=""
        cases={NOUN_CASES}
        columns={SIMPLE_NOUN_COLUMNS}
      />,
    );

    await expect
      .element(screen.getByRole('rowheader', { name: 'Nom.' }))
      .toBeVisible();

    const nomCells = getCaseCells(screen.container, 'Nom.');
    expect(nomCells[0].rowSpan).toBe(2);

    const accCells = getCaseCells(screen.container, 'Acc.');
    expect(accCells.some((c) => c.textContent === 'молоко')).toBe(false);
  });
});

describe('Adjective cell merging (colSpan across genders)', () => {
  it('merges nom male and neuter when they have the same value', async () => {
    const forms: DictionaryForms = {
      'nom am': 'новий',
      'nom an': 'новий',
      'nom af': 'нова',
      'nom ap': 'нові',
      'acc am': 'нового',
      'acc an': 'нове',
      'acc af': 'нову',
      'acc ap': 'нових',
      'gen am': 'нового',
      'gen an': 'нового',
      'gen af': 'нової',
      'gen ap': 'нових',
      'dat am': 'новому',
      'dat an': 'новому',
      'dat af': 'новій',
      'dat ap': 'новим',
      'ins am': 'новим',
      'ins an': 'новим',
      'ins af': 'новою',
      'ins ap': 'новими',
      'loc am': 'новому',
      'loc an': 'новому',
      'loc af': 'новій',
      'loc ap': 'нових',
    };
    const screen = await render(
      <CasesTable
        forms={forms}
        query=""
        cases={ADJ_CASES}
        columns={ADJ_COLUMNS}
      />,
    );

    await expect
      .element(screen.getByRole('rowheader', { name: 'Nom.' }))
      .toBeVisible();

    const nomCells = getCaseCells(screen.container, 'Nom.');
    const mergedCell = nomCells.find((c) => c.colSpan > 1);
    expect(mergedCell).toBeDefined();
    expect(mergedCell!.textContent.normalize('NFC')).toBe('новий');
  });

  it('does NOT merge adj genders when values differ', async () => {
    const forms: DictionaryForms = {
      'nom am': 'великий',
      'nom an': 'велике',
      'nom af': 'велика',
      'nom ap': 'великі',
      'acc am': 'великого',
      'acc an': 'велике',
      'acc af': 'велику',
      'acc ap': 'великих',
      'gen am': 'великого',
      'gen an': 'великого',
      'gen af': 'великої',
      'gen ap': 'великих',
      'dat am': 'великому',
      'dat an': 'великому',
      'dat af': 'великій',
      'dat ap': 'великим',
      'ins am': 'великим',
      'ins an': 'великим',
      'ins af': 'великою',
      'ins ap': 'великими',
      'loc am': 'великому',
      'loc an': 'великому',
      'loc af': 'великій',
      'loc ap': 'великих',
    };
    const screen = await render(
      <CasesTable
        forms={forms}
        query=""
        cases={ADJ_CASES}
        columns={ADJ_COLUMNS}
      />,
    );

    await expect
      .element(screen.getByRole('rowheader', { name: 'Nom.' }))
      .toBeVisible();

    const nomCells = getCaseCells(screen.container, 'Nom.');
    expect(nomCells.every((c) => c.colSpan === 1)).toBe(true);
    expect(nomCells.length).toBe(4);
  });

  it('merges adj gen male and neuter when they share the same value', async () => {
    const forms: DictionaryForms = {
      'nom am': 'синій',
      'nom an': 'синій',
      'nom af': 'синя',
      'nom ap': 'сині',
      'acc am': 'синього',
      'acc an': 'синє',
      'acc af': 'синю',
      'acc ap': 'синіх',
      'gen am': 'синього',
      'gen an': 'синього',
      'gen af': 'синьої',
      'gen ap': 'синіх',
      'dat am': 'синьому',
      'dat an': 'синьому',
      'dat af': 'синій',
      'dat ap': 'синім',
      'ins am': 'синім',
      'ins an': 'синім',
      'ins af': 'синьою',
      'ins ap': 'синіми',
      'loc am': 'синьому',
      'loc an': 'синьому',
      'loc af': 'синій',
      'loc ap': 'синіх',
    };
    const screen = await render(
      <CasesTable
        forms={forms}
        query=""
        cases={ADJ_CASES}
        columns={ADJ_COLUMNS}
      />,
    );

    await expect
      .element(screen.getByRole('rowheader', { name: 'Gen.' }))
      .toBeVisible();

    const genCells = getCaseCells(screen.container, 'Gen.');
    const mergedCell = genCells.find((c) => c.colSpan > 1);
    expect(mergedCell).toBeDefined();
    expect(mergedCell!.textContent).toBe('синього');
  });

  it('can merge more than two adjacent gender columns', async () => {
    const forms: DictionaryForms = {
      'nom am': 'якийсь',
      'nom an': 'якийсь',
      'nom af': 'якийсь',
      'nom ap': 'якісь',
      'acc am': 'якогось',
      'acc an': 'якесь',
      'acc af': 'якусь',
      'acc ap': 'якихось',
      'gen am': 'якогось',
      'gen an': 'якогось',
      'gen af': 'якоїсь',
      'gen ap': 'якихось',
      'dat am': 'якомусь',
      'dat an': 'якомусь',
      'dat af': 'якійсь',
      'dat ap': 'якимось',
      'ins am': 'якимось',
      'ins an': 'якимось',
      'ins af': 'якоюсь',
      'ins ap': 'якимись',
      'loc am': 'якомусь',
      'loc an': 'якомусь',
      'loc af': 'якійсь',
      'loc ap': 'якихось',
    };
    const screen = await render(
      <CasesTable
        forms={forms}
        query=""
        cases={ADJ_CASES}
        columns={ADJ_COLUMNS}
      />,
    );

    await expect
      .element(screen.getByRole('rowheader', { name: 'Nom.' }))
      .toBeVisible();

    const nomCells = getCaseCells(screen.container, 'Nom.');
    const mergedCell = nomCells.find((c) => c.colSpan === 3);
    expect(mergedCell).toBeDefined();
    expect(mergedCell!.textContent.normalize('NFC')).toBe('якийсь');
  });

  it('merges non-adjacent same-valued columns independently', async () => {
    const forms: DictionaryForms = {
      'nom am': 'такий',
      'nom an': 'таке',
      'nom af': 'така',
      'nom ap': 'такі',
      'gen am': 'такого',
      'gen an': 'такого',
      'gen af': 'такої',
      'gen ap': 'таких',
      'dat am': 'такому',
      'dat an': 'такому',
      'dat af': 'такій',
      'dat ap': 'таким',
      'ins am': 'таким',
      'ins an': 'таким',
      'ins af': 'такою',
      'ins ap': 'такими',
      'loc am': 'такому',
      'loc an': 'такому',
      'loc af': 'такій',
      'loc ap': 'таких',
      'acc am': 'такого',
      'acc an': 'таке',
      'acc af': 'таку',
      'acc ap': 'таких',
    };
    const screen = await render(
      <CasesTable
        forms={forms}
        query=""
        cases={ADJ_CASES}
        columns={ADJ_COLUMNS}
      />,
    );

    await expect
      .element(screen.getByRole('rowheader', { name: 'Nom.' }))
      .toBeVisible();

    const nomCells = getCaseCells(screen.container, 'Nom.');
    expect(nomCells.every((c) => c.colSpan === 1)).toBe(true);
  });
});

describe('Verb tables are NOT merged', () => {
  it('verb forms do not use rowSpan or colSpan for merging same-valued cells', async () => {
    const forms = {
      inf: 'бути',
      past: {
        ms: 'був',
        ns: 'було',
        fs: 'була',
        p: 'були',
      },
      pres: {
        '1s': 'є',
        '2s': 'є',
        '3s': 'є',
        '1p': 'є',
        '2p': 'є',
        '3p': 'є',
      },
    };
    const screen = await render(<VerbTable forms={forms} query="" />);

    await expect
      .element(screen.getByRole('rowheader', { name: 'Inf.' }))
      .toBeVisible();

    const allTds = Array.from(
      screen.container.querySelectorAll<HTMLTableCellElement>('td'),
    );
    for (const td of allTds) {
      const text = td.textContent.trim();
      if (text === '–' || text === '') continue;
      if (td.colSpan > 1) {
        expect(td.rowSpan).toBe(1);
      }
    }
  });
});

describe('Exact highlight is applied to merged cells', () => {
  it('merged noun cell gets cell-exact class when query matches', async () => {
    const forms: DictionaryForms = {
      'nom ns': 'будинок',
      'acc ns': 'будинок',
      'gen ns': 'будинку',
      'dat ns': 'будинку',
      'ins ns': 'будинком',
      'loc ns': 'будинку',
      'voc ns': 'будинку',
      'nom np': 'будинки',
      'acc np': 'будинки',
      'gen np': 'будинків',
      'dat np': 'будинкам',
      'ins np': 'будинками',
      'loc np': 'будинках',
      'voc np': 'будинки',
    };
    const screen = await render(
      <CasesTable
        forms={forms}
        query="будинок"
        cases={NOUN_CASES}
        columns={NOUN_COLUMNS}
      />,
    );

    await expect
      .element(screen.getByRole('rowheader', { name: 'Nom.' }))
      .toBeVisible();

    const allTds = Array.from(
      screen.container.querySelectorAll<HTMLTableCellElement>('td'),
    );
    const mergedExactCell = allTds.find(
      (td) => td.rowSpan > 1 && td.textContent === 'будинок',
    );
    expect(mergedExactCell).toBeDefined();
    expect(mergedExactCell!.className).toContain('cell-exact');
  });

  it('merged adjective cell gets cell-exact class when query matches', async () => {
    const forms: DictionaryForms = {
      'nom am': 'новий',
      'nom an': 'новий',
      'nom af': 'нова',
      'nom ap': 'нові',
      'acc am': 'нового',
      'acc an': 'нове',
      'acc af': 'нову',
      'acc ap': 'нових',
      'gen am': 'нового',
      'gen an': 'нового',
      'gen af': 'нової',
      'gen ap': 'нових',
      'dat am': 'новому',
      'dat an': 'новому',
      'dat af': 'новій',
      'dat ap': 'новим',
      'ins am': 'новим',
      'ins an': 'новим',
      'ins af': 'новою',
      'ins ap': 'новими',
      'loc am': 'новому',
      'loc an': 'новому',
      'loc af': 'новій',
      'loc ap': 'нових',
    };
    const screen = await render(
      <CasesTable
        forms={forms}
        query="новий"
        cases={ADJ_CASES}
        columns={ADJ_COLUMNS}
      />,
    );

    await expect
      .element(screen.getByRole('rowheader', { name: 'Nom.' }))
      .toBeVisible();

    const allTds = Array.from(
      screen.container.querySelectorAll<HTMLTableCellElement>('td'),
    );
    const mergedExactCell = allTds.find(
      (td) => td.colSpan > 1 && td.textContent.normalize('NFC') === 'новий',
    );
    expect(mergedExactCell).toBeDefined();
    expect(mergedExactCell!.className).toContain('cell-exact');
  });
});

describe('Cell merging uses runtime values, not static rules', () => {
  it('does not merge noun nom and acc when forms happen to differ', async () => {
    const forms: DictionaryForms = {
      'nom ns': 'хлопець',
      'acc ns': 'хлопця',
      'gen ns': 'хлопця',
      'dat ns': 'хлопцю',
      'ins ns': 'хлопцем',
      'loc ns': 'хлопцеві',
      'voc ns': 'хлопче',
      'nom np': 'хлопці',
      'acc np': 'хлопців',
      'gen np': 'хлопців',
      'dat np': 'хлопцям',
      'ins np': 'хлопцями',
      'loc np': 'хлопцях',
      'voc np': 'хлопці',
    };
    const screen = await render(
      <CasesTable
        forms={forms}
        query=""
        cases={NOUN_CASES}
        columns={NOUN_COLUMNS}
      />,
    );

    await expect
      .element(screen.getByRole('rowheader', { name: 'Nom.' }))
      .toBeVisible();

    const nomCells = getCaseCells(screen.container, 'Nom.');
    expect(nomCells[0].rowSpan).toBe(1);
    expect(nomCells[0].textContent).toBe('хлопець');
  });

  it('merges adj columns based on runtime values, not hardcoded gender rules', async () => {
    const forms: DictionaryForms = {
      'nom am': 'особливий',
      'nom an': 'особливе',
      'nom af': 'особлива',
      'nom ap': 'особливі',
      'gen am': 'особливого',
      'gen an': 'особливого',
      'gen af': 'особливої',
      'gen ap': 'особливих',
      'dat am': 'особливому',
      'dat an': 'особливому',
      'dat af': 'особливій',
      'dat ap': 'особливим',
      'ins am': 'особливим',
      'ins an': 'особливим',
      'ins af': 'особливою',
      'ins ap': 'особливими',
      'loc am': 'особливому',
      'loc an': 'особливому',
      'loc af': 'особливій',
      'loc ap': 'особливих',
      'acc am': 'особливого',
      'acc an': 'особливе',
      'acc af': 'особливу',
      'acc ap': 'особливих',
    };
    const screen = await render(
      <CasesTable
        forms={forms}
        query=""
        cases={ADJ_CASES}
        columns={ADJ_COLUMNS}
      />,
    );

    await expect
      .element(screen.getByRole('rowheader', { name: 'Nom.' }))
      .toBeVisible();
    await expect
      .element(screen.getByRole('rowheader', { name: 'Gen.' }))
      .toBeVisible();

    const nomCells = getCaseCells(screen.container, 'Nom.');
    expect(nomCells.every((c) => c.colSpan === 1)).toBe(true);

    const genCells = getCaseCells(screen.container, 'Gen.');
    const mergedGenCell = genCells.find((c) => c.colSpan > 1);
    expect(mergedGenCell).toBeDefined();
    expect(mergedGenCell!.textContent).toBe('особливого');
  });

  it('handles array-valued forms for merging comparison', async () => {
    const forms: DictionaryForms = {
      'nom ns': ['будинок', 'будиночок'],
      'acc ns': ['будинок', 'будиночок'],
      'gen ns': 'будинку',
      'dat ns': 'будинку',
      'ins ns': 'будинком',
      'loc ns': 'будинку',
      'voc ns': 'будинку',
      'nom np': 'будинки',
      'acc np': 'будинки',
      'gen np': 'будинків',
      'dat np': 'будинкам',
      'ins np': 'будинками',
      'loc np': 'будинках',
      'voc np': 'будинки',
    };
    const screen = await render(
      <CasesTable
        forms={forms}
        query=""
        cases={NOUN_CASES}
        columns={NOUN_COLUMNS}
      />,
    );

    await expect
      .element(screen.getByRole('rowheader', { name: 'Nom.' }))
      .toBeVisible();

    const nomCells = getCaseCells(screen.container, 'Nom.');
    expect(nomCells[0].rowSpan).toBe(2);
  });

  it('only merges adjacent cases, not arbitrary same-valued cases', async () => {
    const forms: DictionaryForms = {
      'nom ns': 'село',
      'acc ns': 'село',
      'gen ns': 'села',
      'dat ns': 'селу',
      'ins ns': 'селом',
      'loc ns': 'селі',
      'voc ns': 'село',
      'nom np': 'села',
      'acc np': 'села',
      'gen np': 'сіл',
      'dat np': 'селам',
      'ins np': 'селами',
      'loc np': 'селах',
      'voc np': 'села',
    };
    const screen = await render(
      <CasesTable
        forms={forms}
        query=""
        cases={NOUN_CASES}
        columns={NOUN_COLUMNS}
      />,
    );

    await expect
      .element(screen.getByRole('rowheader', { name: 'Nom.' }))
      .toBeVisible();
    await expect
      .element(screen.getByRole('rowheader', { name: 'Voc.' }))
      .toBeVisible();

    const nomCells = getCaseCells(screen.container, 'Nom.');
    expect(nomCells[0].rowSpan).toBe(2);

    const vocCells = getCaseCells(screen.container, 'Voc.');
    expect(vocCells[0].rowSpan).toBe(1);
    expect(vocCells[0].textContent).toBe('село');
  });
});

describe('Merge direction depends on part of speech', () => {
  it('nouns merge across cases (rowSpan), not across columns', async () => {
    const forms: DictionaryForms = {
      'nom ns': 'місто',
      'acc ns': 'місто',
      'gen ns': 'міста',
      'dat ns': 'місту',
      'ins ns': 'містом',
      'loc ns': 'місті',
      'voc ns': 'місто',
      'nom np': 'міста',
      'acc np': 'міста',
      'gen np': 'міст',
      'dat np': 'містам',
      'ins np': 'містами',
      'loc np': 'містах',
      'voc np': 'міста',
    };
    const screen = await render(
      <CasesTable
        forms={forms}
        query=""
        cases={NOUN_CASES}
        columns={NOUN_COLUMNS}
      />,
    );

    await expect
      .element(screen.getByRole('rowheader', { name: 'Nom.' }))
      .toBeVisible();

    const allTds = Array.from(
      screen.container.querySelectorAll<HTMLTableCellElement>('td'),
    );
    const hasRowSpan = allTds.some((td) => td.rowSpan > 1);
    const hasColSpan = allTds.some((td) => td.colSpan > 1);
    expect(hasRowSpan).toBe(true);
    expect(hasColSpan).toBe(false);
  });

  it('adjectives merge across genders (colSpan), not across cases', async () => {
    const forms: DictionaryForms = {
      'nom am': 'добрий',
      'nom an': 'добрий',
      'nom af': 'добра',
      'nom ap': 'добрі',
      'acc am': 'доброго',
      'acc an': 'добре',
      'acc af': 'добру',
      'acc ap': 'добрих',
      'gen am': 'доброго',
      'gen an': 'доброго',
      'gen af': 'доброї',
      'gen ap': 'добрих',
      'dat am': 'доброму',
      'dat an': 'доброму',
      'dat af': 'добрій',
      'dat ap': 'добрим',
      'ins am': 'добрим',
      'ins an': 'добрим',
      'ins af': 'доброю',
      'ins ap': 'добрими',
      'loc am': 'доброму',
      'loc an': 'доброму',
      'loc af': 'добрій',
      'loc ap': 'добрих',
    };
    const screen = await render(
      <CasesTable
        forms={forms}
        query=""
        cases={ADJ_CASES}
        columns={ADJ_COLUMNS}
      />,
    );

    await expect
      .element(screen.getByRole('rowheader', { name: 'Nom.' }))
      .toBeVisible();

    const allTds = Array.from(
      screen.container.querySelectorAll<HTMLTableCellElement>('td'),
    );
    const hasColSpan = allTds.some((td) => td.colSpan > 1);
    const hasRowSpan = allTds.some((td) => td.rowSpan > 1);
    expect(hasColSpan).toBe(true);
    expect(hasRowSpan).toBe(false);
  });
});

describe('Separator in merged cells', () => {
  it('uses comma separator instead of line break for colSpan merged cells with array values', async () => {
    const forms: DictionaryForms = {
      'nom am': ['новий', 'новенький'],
      'nom an': ['новий', 'новенький'],
      'nom af': 'нова',
      'nom ap': 'нові',
      'gen am': 'нового',
      'gen an': 'нового',
      'gen af': 'нової',
      'gen ap': 'нових',
      'dat am': 'новому',
      'dat an': 'новому',
      'dat af': 'новій',
      'dat ap': 'новим',
      'ins am': 'новим',
      'ins an': 'новим',
      'ins af': 'новою',
      'ins ap': 'новими',
      'loc am': 'новому',
      'loc an': 'новому',
      'loc af': 'новій',
      'loc ap': 'нових',
      'acc am': 'нового',
      'acc an': 'нове',
      'acc af': 'нову',
      'acc ap': 'нових',
    };
    const screen = await render(
      <CasesTable
        forms={forms}
        query=""
        cases={ADJ_CASES}
        columns={ADJ_COLUMNS}
      />,
    );

    await expect
      .element(screen.getByRole('rowheader', { name: 'Nom.' }))
      .toBeVisible();

    const nomCells = getCaseCells(screen.container, 'Nom.');
    const mergedCell = nomCells.find((c) => c.colSpan > 1);
    expect(mergedCell).toBeDefined();
  });
});

describe('Empty and missing forms', () => {
  it('does not merge empty cells', async () => {
    const forms: DictionaryForms = {
      'nom ns': '',
      'acc ns': '',
      'gen ns': 'тексту',
      'dat ns': 'тексту',
      'ins ns': 'текстом',
      'loc ns': 'тексті',
      'voc ns': 'тексте',
      'nom np': 'тексти',
      'acc np': 'тексти',
      'gen np': 'текстів',
      'dat np': 'текстам',
      'ins np': 'текстами',
      'loc np': 'текстах',
      'voc np': 'тексти',
    };
    const screen = await render(
      <CasesTable
        forms={forms}
        query=""
        cases={NOUN_CASES}
        columns={NOUN_COLUMNS}
      />,
    );

    await expect
      .element(screen.getByRole('rowheader', { name: 'Nom.' }))
      .toBeVisible();

    const nomCells = getCaseCells(screen.container, 'Nom.');
    expect(nomCells[0].rowSpan).toBe(1);
  });

  it('does not merge cells when one has a value and the other is empty', async () => {
    const forms: DictionaryForms = {
      'nom am': 'новий',
      'nom an': '',
      'nom af': 'нова',
      'nom ap': 'нові',
      'gen am': 'нового',
      'gen an': 'нового',
      'gen af': 'нової',
      'gen ap': 'нових',
      'dat am': 'новому',
      'dat an': 'новому',
      'dat af': 'новій',
      'dat ap': 'новим',
      'ins am': 'новим',
      'ins an': 'новим',
      'ins af': 'новою',
      'ins ap': 'новими',
      'loc am': 'новому',
      'loc an': 'новому',
      'loc af': 'новій',
      'loc ap': 'нових',
      'acc am': 'нового',
      'acc an': 'нове',
      'acc af': 'нову',
      'acc ap': 'нових',
    };
    const screen = await render(
      <CasesTable
        forms={forms}
        query=""
        cases={ADJ_CASES}
        columns={ADJ_COLUMNS}
      />,
    );

    await expect
      .element(screen.getByRole('rowheader', { name: 'Nom.' }))
      .toBeVisible();

    const nomCells = getCaseCells(screen.container, 'Nom.');
    expect(nomCells.every((c) => c.colSpan === 1)).toBe(true);
  });
});
