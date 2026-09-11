// Only write the numeric result cells. Python preserves the original XLSX package.
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const mode=process.argv[2] || 'fill';
const source=mode==='final-preview' ? path.join(root,'result1.xlsx') : path.join(root,'附件','附件5','result1.xlsx');
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(source));
if(mode==='fill') {
  const data=JSON.parse(await fs.readFile(path.join(root,'code','outputs','template_values.json'),'utf8'));
  for(const [sheetName, cells] of Object.entries(data)) {
    const sheet=wb.worksheets.getItem(sheetName);
    for(const [cell,value] of Object.entries(cells)) sheet.getRange(cell).values=[[value]];
  }
  wb.recalculate();
  const scan=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!',options:{useRegex:true,maxResults:20}});
  console.log(scan.ndjson);
  await (await SpreadsheetFile.exportXlsx(wb)).save(path.join(root,'code','outputs','artifact_filled.xlsx'));
}
for(const [name,range,key] of [['计划购电量','A1:B12','purchase'],['充放电量','A1:E7','battery']]) {
  const img=await wb.render({sheetName:name,range,scale:2,format:'png'});
  await fs.writeFile(path.join(root,'code','qa',`${mode}_${key}.png`),new Uint8Array(await img.arrayBuffer()));
}
console.log('Spreadsheet rendering/export complete:',mode);
