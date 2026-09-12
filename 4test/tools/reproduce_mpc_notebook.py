"""Execute the notebook and compare all eight PDF/PNG outputs byte-for-byte."""
import hashlib,json,os,sys
from pathlib import Path
import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager
from build_mpc_notebook import build,BASE


def main():
    path=build();book=nbformat.read(path,as_version=4)
    out=BASE/'outputs'/'mpc_notebook_reproduction';out.mkdir(exist_ok=True)
    kernelroot=BASE/'outputs'/'qa'/'kernels';folder=kernelroot/'python3';folder.mkdir(parents=True,exist_ok=True)
    (folder/'kernel.json').write_text(json.dumps({'argv':[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}'],
        'display_name':'Python 3','language':'python'}),encoding='utf-8')
    os.environ['PROBLEM4_FIGURE_DIR']=str(out)
    os.environ.setdefault('IPYTHONDIR',str(BASE/'outputs'/'qa'/'ipython'))
    os.environ.setdefault('JUPYTER_RUNTIME_DIR',str(BASE/'outputs'/'qa'/'jupyter_runtime'))
    km=KernelManager(kernel_name='python3',kernel_spec_manager=KernelSpecManager(kernel_dirs=[str(kernelroot)]))
    NotebookClient(book,timeout=180,km=km,resources={'metadata':{'path':str(BASE)}},allow_errors=False).execute()
    nbformat.write(book,path)
    names=['cost_comparison','monthly_cost_emergency','forecast_accuracy','dispatch_june21']
    hashes={}
    for name in names:
        for suffix in ('.pdf','.png'):
            p=BASE/'figures'/(name+suffix);q=out/(name+suffix)
            a=hashlib.sha256(p.read_bytes()).hexdigest();b=hashlib.sha256(q.read_bytes()).hexdigest()
            assert a==b,(p,q)
            hashes[p.name]=a
    result={'executed_notebook':str(path.relative_to(BASE)),'plots':4,'checked_files':8,
            'byte_identical':True,'sha256':hashes}
    (BASE/'outputs'/'mpc_notebook_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='sha256'},ensure_ascii=False))


if __name__=='__main__':main()
