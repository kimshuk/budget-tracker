const SHEETS = {
  transactions: "transactions",
  merchantCategories: "merchant_categories",
  dashboard: "dashboard",
};

const TRANSACTION_HEADERS = {
  date: "date",
  amount: "amount",
  merchant: "merchant",
  category: "category",
  source: "source",
  memo: "memo",
};

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu("Budget Tracker")
    .addItem("Install automation", "installBudgetTrackerAutomation")
    .addItem("Sync categories and rebuild dashboard", "syncCategoriesAndRebuildDashboard")
    .addToUi();
}

function installBudgetTrackerAutomation() {
  const ss = SpreadsheetApp.getActive();
  ScriptApp.getProjectTriggers()
    .filter((trigger) => trigger.getHandlerFunction() === "handleMerchantCategoryEdit")
    .forEach((trigger) => ScriptApp.deleteTrigger(trigger));

  ScriptApp.newTrigger("handleMerchantCategoryEdit")
    .forSpreadsheet(ss)
    .onEdit()
    .create();

  syncCategoriesAndRebuildDashboard();
}

function handleMerchantCategoryEdit(e) {
  if (!e || !e.range || !isMerchantCategoryEdit_(e.range)) {
    return;
  }
  syncCategoriesAndRebuildDashboard();
}

function syncCategoriesAndRebuildDashboard() {
  const ss = SpreadsheetApp.getActive();
  syncTransactionCategories_(ss);
  rebuildDashboard_(ss);
}

function isMerchantCategoryEdit_(range) {
  const sheet = range.getSheet();
  const startColumn = range.getColumn();
  const endColumn = range.getLastColumn();
  const startRow = range.getRow();
  return (
    sheet.getName() === SHEETS.merchantCategories &&
    startRow > 1 &&
    startColumn <= 2 &&
    endColumn >= 2
  );
}

function syncTransactionCategories_(ss) {
  const transactionsSheet = ss.getSheetByName(SHEETS.transactions);
  const categoriesSheet = ss.getSheetByName(SHEETS.merchantCategories);
  if (!transactionsSheet || !categoriesSheet) {
    return 0;
  }

  const transactionValues = transactionsSheet.getDataRange().getValues();
  if (transactionValues.length <= 1) {
    return 0;
  }

  const categoryMap = getMerchantCategoryMap_(categoriesSheet);
  if (Object.keys(categoryMap).length === 0) {
    return 0;
  }

  const header = transactionValues[0];
  const merchantIndex = header.indexOf(TRANSACTION_HEADERS.merchant);
  const categoryIndex = header.indexOf(TRANSACTION_HEADERS.category);
  if (merchantIndex < 0 || categoryIndex < 0) {
    throw new Error("transactions sheet must contain merchant and category columns");
  }

  let updatedCount = 0;
  for (let i = 1; i < transactionValues.length; i++) {
    const merchant = String(transactionValues[i][merchantIndex] || "").trim();
    const mappedCategory = categoryMap[merchant];
    if (mappedCategory && transactionValues[i][categoryIndex] !== mappedCategory) {
      transactionValues[i][categoryIndex] = mappedCategory;
      updatedCount++;
    }
  }

  if (updatedCount > 0) {
    transactionsSheet
      .getRange(1, 1, transactionValues.length, transactionValues[0].length)
      .setValues(transactionValues);
  }

  return updatedCount;
}

function getMerchantCategoryMap_(sheet) {
  const values = sheet.getDataRange().getValues();
  const result = {};
  values.forEach((row) => {
    const merchant = String(row[0] || "").trim();
    const category = String(row[1] || "").trim();
    if (merchant && category) {
      result[merchant] = category;
    }
  });
  return result;
}

function rebuildDashboard_(ss) {
  const transactionsSheet = ss.getSheetByName(SHEETS.transactions);
  if (!transactionsSheet) {
    return;
  }

  const transactions = parseTransactions_(transactionsSheet.getDataRange().getValues());
  const dashboard = getOrCreateSheet_(ss, SHEETS.dashboard);
  const dashboardModel = buildDashboardModel_(transactions);

  resetDashboardSheet_(dashboard);
  if (dashboardModel.rows.length === 0) {
    return;
  }

  dashboard
    .getRange(1, 1, dashboardModel.rows.length, 4)
    .setValues(dashboardModel.rows);

  applyDashboardFormatting_(dashboard, dashboardModel);
  applyRowGroups_(dashboard, dashboardModel.groups);
  applyCharts_(dashboard, dashboardModel);
}

function parseTransactions_(values) {
  if (values.length <= 1) {
    return [];
  }

  const header = values[0];
  const dateIndex = header.indexOf(TRANSACTION_HEADERS.date);
  const amountIndex = header.indexOf(TRANSACTION_HEADERS.amount);
  const merchantIndex = header.indexOf(TRANSACTION_HEADERS.merchant);
  const categoryIndex = header.indexOf(TRANSACTION_HEADERS.category);
  const sourceIndex = header.indexOf(TRANSACTION_HEADERS.source);
  const memoIndex = header.indexOf(TRANSACTION_HEADERS.memo);

  return values.slice(1)
    .filter((row) => row.length > categoryIndex && row[dateIndex] && row[amountIndex])
    .map((row) => {
      const date = parseTransactionDate_(row[dateIndex]);
      return {
        date: date,
        year: date.getFullYear(),
        month: date.getMonth() + 1,
        amount: Number(row[amountIndex]) || 0,
        merchant: String(row[merchantIndex] || ""),
        category: String(row[categoryIndex] || "미분류"),
        source: sourceIndex >= 0 ? String(row[sourceIndex] || "") : "",
        memo: memoIndex >= 0 ? String(row[memoIndex] || "") : "",
      };
    });
}

function parseTransactionDate_(value) {
  if (value instanceof Date) {
    return value;
  }
  const parts = String(value).slice(0, 10).split(/[-.]/).map(Number);
  return new Date(parts[0], parts[1] - 1, parts[2]);
}

function buildDashboardModel_(transactions) {
  const byMonth = {};
  const byYear = {};
  transactions.forEach((txn) => {
    const monthKey = monthKey_(txn.year, txn.month);
    if (!byMonth[monthKey]) byMonth[monthKey] = [];
    if (!byYear[txn.year]) byYear[txn.year] = [];
    byMonth[monthKey].push(txn);
    byYear[txn.year].push(txn);
  });

  const rows = [];
  const groups = [];
  const percentRanges = [];
  const barCharts = [];

  const monthKeys = Object.keys(byMonth).sort(compareMonthKeysDesc_);
  if (monthKeys.length >= 2) {
    const latestKey = monthKeys[0];
    const previousKey = monthKeys[1];
    const latestLabel = monthLabelFromKey_(latestKey);
    const previousLabel = monthLabelFromKey_(previousKey);
    const latestTotals = categoryTotals_(byMonth[latestKey]);
    const previousTotals = categoryTotals_(byMonth[previousKey]);
    const categories = uniqueSorted_(Object.keys(latestTotals).concat(Object.keys(previousTotals)));

    rows.push(["최근 2개월 카테고리 비교", "", "", ""]);
    rows.push(["카테고리", latestLabel, previousLabel, ""]);
    const start = rows.length;
    categories.forEach((category) => {
      rows.push([category, latestTotals[category] || 0, previousTotals[category] || 0, ""]);
    });
    const end = rows.length;
    if (end > start) {
      barCharts.push({
        title: `${latestLabel} vs ${previousLabel} 카테고리 지출 비교`,
        start: start,
        end: end,
        anchor: 0,
      });
    }
    while (rows.length < topSectionRowCount_(transactions)) {
      rows.push(["", "", "", ""]);
    }
  }

  Object.keys(byYear).sort((a, b) => Number(b) - Number(a)).forEach((year) => {
    const yearTransactions = byYear[year];
    rows.push([`${year}년`, "", "연간 총 지출", sumAmounts_(yearTransactions)]);

    const months = uniqueSorted_(yearTransactions.map((txn) => txn.month)).sort((a, b) => b - a);
    months.forEach((month) => {
      const monthTransactions = byMonth[monthKey_(Number(year), month)];
      const monthTotal = sumAmounts_(monthTransactions);
      const totals = categoryTotals_(monthTransactions);
      const categories = Object.keys(totals).sort();

      rows.push([`${year}년 ${month}월`, "", "월 총 지출", monthTotal]);
      rows.push(["카테고리", "비율", "금액", ""]);

      const summaryStart = rows.length;
      categories.forEach((category) => {
        rows.push([category, monthTotal ? totals[category] / monthTotal : 0, totals[category], ""]);
      });
      const summaryEnd = rows.length;
      if (summaryEnd > summaryStart) {
        percentRanges.push({
          start: summaryStart,
          end: summaryEnd,
        });
      }

      rows.push(["", "", "", ""]);
      rows.push(["거래 상세", "", "", ""]);

      categories.forEach((category) => {
        const categoryTransactions = monthTransactions
          .filter((txn) => txn.category === category)
          .sort((a, b) => a.date.getTime() - b.date.getTime());
        rows.push([category, "", totals[category], ""]);

        const detailStart = rows.length;
        categoryTransactions.forEach((txn) => {
          rows.push(["", formatDate_(txn.date), txn.merchant, txn.amount]);
        });
        const detailEnd = rows.length;
        if (detailEnd > detailStart) {
          groups.push({ start: detailStart, end: detailEnd });
        }
      });

      rows.push(["", "", "", ""]);
    });

    rows.push(["", "", "", ""]);
  });

  return { rows: rows, groups: groups, percentRanges: percentRanges, barCharts: barCharts };
}

function resetDashboardSheet_(sheet) {
  sheet.getCharts().forEach((chart) => sheet.removeChart(chart));
  sheet.getRange(1, 1, sheet.getMaxRows(), sheet.getMaxColumns()).breakApart();
  sheet.clear();
  if (sheet.getMaxRows() > 0) {
    sheet.showRows(1, sheet.getMaxRows());
  }
  try {
    sheet.expandAllRowGroups();
    sheet.getRange(1, 1, sheet.getMaxRows(), 1).shiftRowGroupDepth(-8);
  } catch (err) {
    // No existing row groups, or Google Sheets refused a no-op depth shift.
  }
}

function applyDashboardFormatting_(sheet, model) {
  const rowCount = model.rows.length;
  sheet.getRange(1, 3, rowCount, 2).setNumberFormat("₩#,##0");

  model.percentRanges.forEach((range) => {
    sheet.getRange(range.start + 1, 2, range.end - range.start, 1).setNumberFormat("0.0%");
  });

  model.barCharts.forEach((chart) => {
    sheet.getRange(chart.start + 1, 2, chart.end - chart.start, 2).setNumberFormat("₩#,##0");
  });

  applyDashboardStyles_(sheet, model.rows);
}

function applyDashboardStyles_(sheet, rows) {
  const blue = "#a4c2f4";
  const green = "#b6d7a8";
  const yellow = "#ffe599";

  sheet.setColumnWidth(1, 140);
  sheet.setColumnWidth(2, 130);
  sheet.setColumnWidth(3, 170);
  sheet.setColumnWidth(4, 120);
  sheet.setColumnWidth(5, 40);
  for (let column = 6; column <= 9; column++) {
    sheet.setColumnWidth(column, 155);
  }

  rows.forEach((row, index) => {
    const rowNumber = index + 1;
    const label = String(row[0] || "");
    if (label === "최근 2개월 카테고리 비교") {
      styleRange_(sheet.getRange(rowNumber, 1, 1, 3), blue, true, "center");
    } else if (label === "카테고리" || label === "거래 상세") {
      styleRange_(sheet.getRange(rowNumber, 1, 1, 3), green, true, "center");
    } else if (label.endsWith("년") || label.endsWith("월")) {
      styleRange_(sheet.getRange(rowNumber, 1, 1, 4), blue, true);
      if (row[2] === "연간 총 지출" || row[2] === "월 총 지출") {
        styleRange_(sheet.getRange(rowNumber, 4, 1, 1), yellow, true);
      }
    }
  });
}

function styleRange_(range, background, bold, horizontalAlignment) {
  range
    .setBackground(background)
    .setFontWeight(bold ? "bold" : "normal")
    .setBorder(true, true, true, true, true, true);
  if (horizontalAlignment) {
    range.setHorizontalAlignment(horizontalAlignment);
  }
}

function applyRowGroups_(sheet, groups) {
  groups.forEach((group) => {
    sheet
      .getRange(group.start + 1, 1, group.end - group.start, 1)
      .shiftRowGroupDepth(1)
      .collapseGroups();
  });
}

function applyCharts_(sheet, model) {
  model.barCharts.forEach((chart) => {
    const chartRange = sheet.getRange(chart.start, 1, chart.end - chart.start + 1, 3);
    sheet.insertChart(
      sheet.newChart()
        .setChartType(Charts.ChartType.BAR)
        .addRange(chartRange)
        .setPosition(chart.anchor + 1, 6, 0, 0)
        .setOption("title", chart.title)
        .setOption("width", 640)
        .setOption("height", 360)
        .setOption("legend", { position: "right" })
        .setOption("hAxis.title", "지출")
        .setOption("vAxis.title", "카테고리")
        .build()
    );
  });
}

function getOrCreateSheet_(ss, name) {
  return ss.getSheetByName(name) || ss.insertSheet(name);
}

function categoryTotals_(transactions) {
  const totals = {};
  transactions.forEach((txn) => {
    totals[txn.category] = (totals[txn.category] || 0) + txn.amount;
  });
  return totals;
}

function sumAmounts_(transactions) {
  return transactions.reduce((sum, txn) => sum + txn.amount, 0);
}

function monthKey_(year, month) {
  return `${year}-${String(month).padStart(2, "0")}`;
}

function compareMonthKeysDesc_(a, b) {
  return b.localeCompare(a);
}

function topSectionRowCount_(transactions) {
  const byMonth = {};
  transactions.forEach((txn) => {
    const key = monthKey_(txn.year, txn.month);
    if (!byMonth[key]) byMonth[key] = [];
    byMonth[key].push(txn);
  });
  const monthKeys = Object.keys(byMonth).sort(compareMonthKeysDesc_).slice(0, 2);
  if (monthKeys.length < 2) {
    return 12;
  }
  const categories = {};
  monthKeys.forEach((key) => {
    byMonth[key].forEach((txn) => {
      categories[txn.category] = true;
    });
  });
  return Math.max(2 + Object.keys(categories).length + 1, 12);
}

function monthLabelFromKey_(key) {
  const parts = key.split("-");
  return `${Number(parts[0])}년 ${Number(parts[1])}월`;
}

function uniqueSorted_(values) {
  return Array.from(new Set(values)).sort();
}

function formatDate_(date) {
  return Utilities.formatDate(date, Session.getScriptTimeZone(), "yyyy-MM-dd");
}
