# LAREX Action Starter Template

Starter template for developing [LAREX Actions](https://github.com/OCR4all/LAREX) using the [larex-action-sdk](https://github.com/OCR4all/larex-action-sdk).

## Overview

The template is intentionally minimal. Action-specific functionality should be added where indicated by `TEMPLATE` comments.

For more information, read the [official LAREX documentation](https://docs.larex.kallimachos.de/actions/overview).

## File Structure

```bash
├─ src/larex_action/
│  ├─ __init__.py  # Action entrypoint. Defines the logger, parameter provider, and endpoints
│  ├─ config.py    # Environment and runtime configuration definitions
│  ├─ runner.py    # Action communication, state management, and worker initialization
│  └─ worker.py    # Actual action processing
├─ action.yml      # Action definition
├─ compose.yml     # Docker/Podman Compose definition
├─ template.env    # Environment template
└─ ...
```

## Template

### Pull Data from LAREX

Data can be pulled either by using `ctx.download_bytes()` (recommended) or `ctx.download_to_path()`.

Example:

```python
# runner.py
image = await ctx.download_bytes(page.images[0])
xml = await ctx.download_bytes(page.xml[0])
```

### Push Data to LAREX

The template automatically initializes an empty `results` object for each processed page and sends the object at the end. To add data to the results, use either `results.add_file_bytes()`, `results.add_image_bytes()`, or `results.add_xml_bytes()` to add bytes directly, or add files by path with `results.add_file_path()`, `results.add_image_path()`, or `results.add_xml_path()`.

Example:

```python
# runner.py
results.add_xml_bytes(page_id=page.id, content=xml_bytes, file_name=f'{page.name}.xml')
```

### Set Up the Worker

Each worker is started in a separate process to prevent an indefinitely running action if a worker crashes. Communication between the action process and the worker process is handled through a `multiprocessing.Pipe`. This is already implemented.

To change the data transferred between the processes, modify the two dataclasses `WorkerRequest` (data sent to the worker) and `WorkerSuccess` (data received from the worker on success).

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

Within the worker, libraries can be initialized before the processing loop. This is executed once per action run and can be used, for example, to load a model.

Example:

```python
# worker.py
def work(connection: Connection) -> None:
    import numpy as np
    from my_model import Model
    m = Model(model)
    ...
```

Within the empty try/catch block, the actual action processing can be implemented. Received data is accessed via the `request` object (of type `WorkerRequest`) and sent back to the main process via `connection.send()`, which accepts a `WorkerSuccess` object.

Example:

```python
# worker.py
try:
    image = cv2.imdecode(np.frombuffer(request.image, np.uint8), cv2.IMREAD_GRAYSCALE)
    xml = do_something(image)
    connection.send(WorkerSuccess(xml))
except ...
```

### Action Parameters

*Action parameters* are custom values that can be manually set or changed in the LAREX frontend for each action run.

First, they have to be defined in the action definition. See the [documentation](https://docs.larex.kallimachos.de/actions/yaml-reference#parameters) for further information.

Example:

```yml
# action.yml
parameters:
  Model:  # This is the name displayed in the frontend
    type: string
    default: model-a
```

To access the parameters inside the action, use `action_input.parameters.get()`.

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
    args=(child_connection, model,)  # This is the argument list
)
```

Additionally, the worker function needs to accept the argument, for example:

```python
# worker.py
def work(connection: Connection, model: Path) -> None:
    ...
```

### Define Parameter Value Providers

In some cases, you may want to provide a dynamic list of possible parameter values to the frontend (e.g., a list of available models). For this case, you can specify *parameter value providers*.

Example:

```python
# __init__.py
from larex_actions import ParameterChoice

def discover_models() -> list[ParameterChoice]:
    return [ParameterChoice(value=path.name, label=path.stem) for path in Path('/models').glob('*.pth')]
```

A *parameter value provider* can then be registered in the app with:

```python
# __init__.py
app = create_larex_action_app(
    ...
    parameter_value_providers={'models': discover_models}
)
```

Finally, the provider has to be registered in the action definition:

```yml
# action.yml
parameters:
  Model:
    type: string
    default: model-a
    allowedValues:
      provider: models
```

### Add Custom Configuration Variables

In addition to the already defined and required variables in `template.env` and `config.py`, you may sometimes want to add custom variables (e.g., file paths, fixed parameters, etc.). To do this, simply add the variable to the `Settings` class. The value can then be passed as an environment variable to the action or container. Required variables are explained further in the *Deploy* section.

## Deploy

### Environment

Create a `.env` file from the template and populate its values:

```bash
cp template.env .env
```

| **Variable**                     | **Default** | **Description**                                                                                                               |
| -------------------------------- | ----------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `PORT`                           | required    | The port on which the action endpoints are exposed.                                                                           |
| `LAREX_PROCESSOR_ID`             | required    | Processor ID expected in dispatch headers.                                                                                    |
| `LAREX_DISPATCH_HMAC_SECRET`     | required    | Shared dispatch HMAC secret generated by LAREX.                                                                               |
| `LAREX_ALLOWED_CALLBACK_ORIGINS` | required    | Comma-separated LAREX callback origins accepted by the SDK.                                                                   |
| `LAREX_ROUTE_PREFIXES`           | required    | Optional comma-separated route prefixes, for example `/kraken`, that also expose prefixed `/dispatch` and health routes.      |
| `LAREX_SDK_TRANSPORT_DEBUG`      | `false`     | Set to `true` to log SDK pulls, heartbeats, downloads, uploads, retries, and failures locally.                                |
| `ACTION_DEBUG`                   | `false`     | Enable action worker logging.                                                                                                 |
| `ACTION_MAX_CONCURRENT_RUNS`     | `1`         | Maximum number of worker runs admitted concurrently in one processor instance. Increase only after measuring host/GPU memory. |
| `ACTION_PAGE_TIMEOUT`            | `None`      | Maximum processing time per page in seconds. If a page exceeds the timeout, the process is cancelled.                         |

### Docker/Podman Compose (Recommended)

You may want to change the `name` and `container_name` in `compose.yml` if you host multiple actions.

```bash
docker compose build && docker compose up -d
```

#### Pass directories to the container

Add a volume to the service:
```yml
volumes:
  - /path/on/server:/path/in/container:Z
```

The `:Z` suffix might be necessary if your server has SELinux installed.

#### Pass GPU(s) to the container


Add this to the compose file:
```yml
devices:
  - nvidia.com/gpu=all
security_opt:
  - label=disable
```
