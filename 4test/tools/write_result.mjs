// 官方模板的读取、扩展、写入、检查和渲染。
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const base = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const project = path.resolve(base, "..");
const template = path.join(project, "附件", "附件5", "result4-2.xlsx");
const mode = "write";
const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(template));
const qa = path.join(base, "outputs", "qa");
await fs.mkdir(qa, {recursive: true});

async function render(name, range, suffix) {
  const image = await wb.render({sheetName: name, range, scale: 1.5, format: "png"});
  await fs.writeFile(path.join(qa, `${suffix}.png`), new Uint8Array(await image.arrayBuffer()));
}

if (mode === "write") {
  const payload = JSON.parse(await fs.readFile(path.join(base, "outputs", "excel_payload.json"), "utf8"));
  const plan = wb.worksheets.getItem("计划购电量");
  // 原模板表头原样保留；列与实际物理区间的对应关系另存time_mapping.csv。
  plan.getRange("B2:EQ335").values = payload.plan_values;
  plan.getRange("B2:EQ335").format.numberFormat = "0.000000";
  plan.freezePanes.freezeRows(1);
  plan.freezePanes.freezeColumns(1);

  const battery = wb.worksheets.getItem("充放电量");
  const bRows = [["日期","时间段","充电量","放电量","时刻","储电量"], ...payload.battery_rows.map(r => [
    new Date(`${r.date}T00:00:00Z`), r.time_range, r.charge_kwh, r.discharge_kwh, r.time, r.soc_kwh === "" ? null : r.soc_kwh
  ])];
  battery.getRange(`A1:F${Math.max(20,bRows.length)}`).clear({applyTo:"contents"});
  battery.getRange("A1").write(bRows);
  battery.getRange(`A2:A${bRows.length}`).format.numberFormat = "yyyy-mm-dd";
  battery.getRange(`C2:F${bRows.length}`).format.numberFormat = "0.000000";
  battery.getRange(`A1:F${bRows.length}`).format.font = {name:"Arial",size:10};
  battery.getRange("A1:F1").format = {fill:"#D9EAF7",font:{name:"Arial",size:10,bold:true,color:"#1F2937"}};
  battery.getRange(`A1:F${bRows.length}`).format.verticalAlignment = "center";
  battery.getRange(`A1:F${bRows.length}`).format.autofitColumns();
  battery.freezePanes.freezeRows(1);

  const emergency = wb.worksheets.getItem("紧急购电量");
  const eRows = [["日期","购电时间段","购电量"], ...payload.emergency_rows.map(r => [
    new Date(`${r.date}T00:00:00Z`), r.time_range, r.emergency_kwh
  ])];
  emergency.getRange(`A1:C${Math.max(11,eRows.length)}`).clear({applyTo:"contents"});
  emergency.getRange("A1").write(eRows);
  if (eRows.length > 1) {
    emergency.getRange(`A2:A${eRows.length}`).format.numberFormat = "yyyy-mm-dd";
    emergency.getRange(`C2:C${eRows.length}`).format.numberFormat = "0.000000";
  }
  emergency.getRange(`A1:C${eRows.length}`).format.font = {name:"Arial",size:10};
  emergency.getRange("A1:C1").format = {fill:"#D9EAF7",font:{name:"Arial",size:10,bold:true,color:"#1F2937"}};
  emergency.getRange(`A1:C${eRows.length}`).format.autofitColumns();
  emergency.freezePanes.freezeRows(1);

  wb.recalculate();
  const errors = await wb.inspect({kind:"match",searchTerm:"#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!",options:{useRegex:true,maxResults:50}});
  await fs.writeFile(path.join(base,"outputs","excel_formula_scan.ndjson"), errors.ndjson || "", "utf8");
  const output = await SpreadsheetFile.exportXlsx(wb);
  let outputPath = payload.output_path;
  try {
    await output.save(outputPath);
  } catch (error) {
    if (!["EBUSY", "EPERM"].includes(error.code)) throw error;
    // Excel打开原结果时不强行关闭应用，先保存可验收的同名副本。
    outputPath = path.join(base, "outputs", "template_preserved", "result4-2.xlsx");
    await fs.mkdir(path.dirname(outputPath), {recursive:true});
    await output.save(outputPath);
  }
  await fs.writeFile(path.join(base,"outputs","workbook_export.json"),
    JSON.stringify({output_path:outputPath, requested_path:payload.output_path}), "utf8");
  await render("计划购电量","A1:H8","result4-2_plan");
  await render("充放电量","A1:F14","result4-2_battery");
  await render("紧急购电量",`A1:C${Math.min(eRows.length,18)}`,"result4-2_emergency");
  console.log(JSON.stringify({output:outputPath, planRows:payload.plan_values.length,
    batteryRows:payload.battery_rows.length, emergencyRows:payload.emergency_rows.length}));
} else {
  await render("计划购电量","A1:H8","template_plan");
  await render("充放电量","A1:F14","template_battery");
  await render("紧急购电量","A1:C11","template_emergency");
  console.log("Template preview complete");
}
