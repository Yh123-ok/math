"""实际执行Notebook，并逐字节核对重新绘制的10组PDF/PNG。"""
import json,os,sys,hashlib
from pathlib import Path
import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager
from build_notebook import build,BASE


def main():
    path=build();book=nbformat.read(path,as_version=4)
    out=BASE/'outputs/notebook_reproduction';out.mkdir(exist_ok=True)
    kernelroot=BASE/'outputs/qa/kernels';folder=kernelroot/'python3';folder.mkdir(parents=True,exist_ok=True)
    (folder/'kernel.json').write_text(json.dumps({'argv':[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}'],
        'display_name':'Python 3','language':'python'}),encoding='utf-8')
    os.environ['PROBLEM4_FIGURE_DIR']=str(out)
    os.environ.setdefault('IPYTHONDIR',str(BASE/'outputs/qa/ipython'))
    os.environ.setdefault('JUPYTER_RUNTIME_DIR',str(BASE/'outputs/qa/jupyter_runtime'))
    km=KernelManager(kernel_name='python3',kernel_spec_manager=KernelSpecManager(kernel_dirs=[str(kernelroot)]))
    client=NotebookClient(book,timeout=180,km=km,resources={'metadata':{'path':str(BASE/'notebooks')}},allow_errors=False)
    client.execute();nbformat.write(book,path)
    checks={}
    for p in sorted((BASE/'figures').glob('*')):
        if p.suffix not in ('.pdf','.png'):continue
        new=out/p.name
        a=hashlib.sha256(p.read_bytes()).hexdigest();b=hashlib.sha256(new.read_bytes()).hexdigest()
        checks[p.name]={'original_sha256':a,'notebook_sha256':b,'identical':a==b}
    assert len(checks)==20 and all(r['identical'] for r in checks.values()),checks
    result={'executed_notebook':str(path.relative_to(BASE)),'code_cells_executed':sum(c.cell_type=='code' for c in book.cells),
        'plots':10,'pdf_and_png_files':20,'all_byte_identical':True,'files':checks}
    (BASE/'outputs/notebook_reproduction.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    manifest_path=BASE/'outputs/manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest['outputs_sha256'][str(path.relative_to(BASE))]=hashlib.sha256(path.read_bytes()).hexdigest()
    manifest['notebook_reproduction']='20 PDF/PNG files byte-identical after kernel execution'
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='files'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
