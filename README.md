# LAREX Action Starter Template

Starter template for developing [LAREX Actions](https://github.com/OCR4all/LAREX) using the [larex-actions-sdk](https://github.com/OCR4all/larex-action-sdk).


## Overview

The template is intentionally minimal. Action-specific functionality should be added where indicated by `TEMPLATE` comments.

For more information, read the [official LAREX documentation](https://docs.larex.kallimachos.de/actions/overview).


## File Structure

```bash
├─ src/larex_action/
│  ├─ __init__.py  # Action entrypoint. Defines logger, parameter provider and endpoints
│  ├─ config.py    # Environment and runtime config definitions
│  ├─ runner.py    # Action communication, states, worker initialization
│  └─ worker.py    # Actual action processing
├─ action.yml      # Action definition
├─ compose.yml     # Docker/Podman compose definition
├─ template.env    # Environment template
└─ ...
```


## Template

### Pull data from LAREX

Data can be bulled either by `ctx.download_bytes()` (recommended) or by `ctx.download_to_path()`.

Example:
```python
# runner.py
image = await ctx.download_bytes(page.images[0])
xml = await ctx.download_bytes(page.xml[0])
```


### Push data to LAREX

The template automatically initializes an empty `results` object for each processed page and sends the object at the end. To add data to the results, use either `results.add_file_bytes()`, `results.add_image_bytes()` or `results.add_xml_bytes()` to add bytes directly, or add files by path with `results.add_file_path()`, `results.add_image_path()` or `results.add_xml_path()`.

Example:
```python
# runner.py
results.add_xml_bytes(page_id=page.id, content=xml_bytes, file_name=f'{page.name}.xml')
```


### Setup worker

Each worker is started in a separate process to prevent infinite running actions on worker crashes. Data between the action process and the worker process is transfered through a `multiprocessing.Pipe`. This is already implemented.

To change the transfered data objects, change the two dataclasses `WorkerRequest` (data sent to the worker) and `WorkerSuccess` (data received from the worker on success).

Example:
```python
# worker.py
@dataclass
class WorkerRequest:
    image: bytes
    xml: bytes
    
@dataclass
class WorkerSuccess:
    xml: bytes
```

Within the worker, libraries can be initialized before the processing loop. This is executed once per action run and can be used to e.g. load a model.

Example:
```python
# worker.py
def work(connection: Connection) -> None:
    import numpy as np
    from my_model import Model
    m = Model(model)
    ...
```

Within the empty try/catch, the actual action processing can be implemented. Received data is accessed via the `request` object (of type `WorkerRequest`) and sent back to the main process via `connection.send()`, which accepts a `WorkerSuccess` object.

Example:
```python
# worker.py
try:
    image = cv2.imdecode(np.frombuffer(request.image, np.uint8), cv2.IMREAD_GRAYSCALE)
    xml = do_something(image)            
    connection.send(WorkerSuccess(xml))
except ...
```

### Action parameters

_Action parameters_ are custom values that can be manually set or changed in the LAREX frontend for each action run.

First, they have to be defined in the action definition. See the [documentation](https://docs.larex.kallimachos.de/actions/yaml-reference#parameters) for further information.

Example:
```yml
# action.yml
parameters:
  Model:  # this is the name displayed in the frontend
    type: string
    default: model-a
```

To pull the parameters inside the action, use `action_input.parameters.get()`.

Example:
```python
# runner.py
model = action_input.parameters.get('Model', None)
```

If you need to pass a parameter to the worker, you have to pass the value as a process argument:
```python
# runner.py
process = context.Process(
    target=work,
    args=(child_connection, model, )  # this is the argument list
)
```

Additionally, the worker function needs to accept such an argument, for example:
```python
# worker.py
def work(connection: Connection, model: Path) -> None:
    ...
```

### Define parameter value providers

In some cases, you want to provide a dynamic list of possible parameters to the frontend (e.g. a list of available models). For this case, you can specify _parameter value providers_. 

Example:
```python
# __init__.py
from larex_actions import ParameterChoice

def discover_models() -> list[ParameterChoice]:
    return [ParameterChoice(value=path.name, label=path.stem) for path in Path('/models').glob('*.pth')]
```

A _parameter value provider_ can then be registered in the app with:
```python
# __init__.py
app = create_larex_action_app(
    ...
    parameter_value_providers={'models': discover_models}
)
```

Last but not least, the provider has to be registered in the action definition:
```yml
# action.yml
parameters:
  Model:
    type: string
    default: model-a
    allowedValues:
      provider: models
```

### Add custom config variables

Next to the already defined and required variables in `template.env` and `config.py`, sometimes you want to add custom variables (e.g. file paths, fixed parameters, etc.). For this, just add the variable to the `Settings` class. The value can then be passed as an environment variable to the action or container. Required variables are further explained in the _Deploy_ section.

## Deploy

### Environment

Create a `.env` file from the template and populate its values:
```bash
cp template.env .env
```

| **Variable**                     | **Default** | **Description**                                                                                                           |
|----------------------------------|-------------|---------------------------------------------------------------------------------------------------------------------------|
| `PORT`                           | required    | The port the expose the action endpoints to.                                                                              |
| `LAREX_PROCESSOR_ID`             | required    | Processor id expected in dispatch headers.                                                                                |
| `LAREX_DISPATCH_HMAC_SECRET`     | required    | Shared dispatch HMAC secret generated by LAREX.                                                                           |
| `LAREX_ALLOWED_CALLBACK_ORIGINS` | required    | comma-separated LAREX callback origins accepted by the SDK.                                                               |
| `LAREX_ROUTE_PREFIXES`           | required    | Optional comma-separated route prefixes, for example `/kraken`, that also expose prefixed `/dispatch`, and health routes. |
| `LAREX_SDK_TRANSPORT_DEBUG`      | `false`     | Set to true to log SDK pulls, heartbeats, downloads, uploads, retries, and failures locally.                              |
| `ACTION_DEBUG`                   | `false`     | Enable action worker logging                                                                                              |
| `ACTION_MAX_CONCURRENT_RUNS`     | `1`         | Maximum worker runs admitted concurrently in one processor instance. Increase only after measuring host/GPU memory.       |
| `ACTION_PAGE_TIMEOUT`            | `None`      | Maximum processing time per page in seconds. If a page exceeds the timeout, the process is cancelled.                     |

### Docker/Podman Compose (recommended)

You might want to change the container name in `compose.yml` if you host multiple actions.

```bash
docker compose build && docker compose up -d
```
