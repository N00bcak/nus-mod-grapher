# nus-mod-grapher
Extracts and renders subgraphs of the entire NUS module catalogue. I do not need any other reason to do this.

## Installation Command (Linux Only)
Linux:
```
sudo apt-get install graphviz graphviz-dev; python -m pip install -r requirements.txt
```

## How to use this repository
After installing all the prerequisites, run
`python nus-mod-grapher --help`

Select your arguments before executing the module.

**Your output will be a .dot file**, which you can render with GraphViz CLI (see docs [here](https://graphviz.org/documentation/))
or submit for further processing through graph analysis libraries like [Networkx](https://networkx.org/documentation/stable/index.html).