# LAREX Action Starter Template

Starter template for developing [LAREX Actions](https://github.com/OCR4all/LAREX) using the [larex-actions-sdk](https://github.com/OCR4all/larex-action-sdk).

The template is intentionally minimal. Action-specific functionality should be added where indicated by `TEMPLATE` comments.

For more information, read the [official documentation](https://docs.larex.kallimachos.de/actions/overview).

## Project Structure
```text
├─ src/larex_action/
│  ├─ __init__.py
│  ├─ config.py
│  ├─ runner.py
│  └─ worker.py
├─ action.yml
├─ compose.yml
├─ template.env
└─ ...
```

### \_\_init\_\_.py

This module is the entry point of the LAREX Action.

#### Parameter value providers

The template includes an example for parameter value providers. Parameter value providers can be used when an action parameter has a dynamically generated set of possible values.
For example, an action that uses models stored in `/models` could expose the available model files as parameter choices:

Provider example:
```python
from pathlib import Path
from larex_actions import ParameterChoice

def discover_models() -> list[ParameterChoice]:
    return [ParameterChoice(value=path.name, label=path.stem) for path in Path('/models').glob('*.pth')]
```

The provider is then registered with the application:
```python
app = create_larex_action_app(
    ...,
    parameter_value_providers={'models': discover_models}
)
```

### config.py

This module contains the configuration for the action. Settings are loaded from environment variables using [Pydantic Settings](https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/) and are available throughout the application through the `env` object.

Settings example:
```python
class Settings(BaseSettings):
    ...
    MODEL_PATH: str = '/models/default.pth' 
    USE_GPU: bool = True 
    MAX_BATCH_SIZE: PositiveInt = 1
    ...
```

Add only configuration that is specific to the action. The LAREX and generic action settings already provided by the template should normally be left unchanged.


### runner.py

This module coordinates the execution of the LAREX Action. It connects the LAREX _ActionContext_ with the process-isolated worker defined in `worker.py`. It also handles cancellation, progress reporting, timeouts, worker lifecycle management, and concurrent action limits.

#### Pass parameters to the action

Example of a `Model` parameter:
```python
model = action_input.parameters.get('Model', None)
```

In most cases, the parameter needs to be passed to the worker, which is done by adding it to the parameter list:
```python
process = context.Process(
    target=work,
    args=(child_connection, model, )  # added here
)
```

The `work` function in `worker.py` then has to accept such a parameter as well!

which accepts parameters from the LAREX frontend. A parameter can be defined in the action definition:
```yaml
parameters:
  Model:
    type: string
    description: Select a model
    default: model.pth
    allowedValues:
      provider: models
```

The full documentation can be found [here](https://docs.larex.kallimachos.de/actions/yaml-reference#parameters).

#### Pull inputs from LAREX

This is where data required to process the current page should be retrieved from LAREX and sent to the worker.

Example if an image and a xml file is sent:
```python
image = await ctx.download_bytes(page.images[0])
xml = await ctx.download_bytes(page.xml[0])
connection.send(WorkerRequest(image, xml))
```

The corresponding fields should be added to `WorkerRequest` in `worker.py`. Keep LAREX-specific data retrieval in the runner. The worker should receive ordinary Python data through `WorkerRequest` rather than accessing the `ActionContext` itself.

#### Handling worker results

The worker returns either a `WorkerSuccess` or `WorkerFailure`. Depending on the result, the corresponding fields should be added to `WorkerSuccess`.

For example, if `WorkerSuccess` contains an XML document:
```python
results.add_xml_bytes(
    page_id=page.id, 
    content=result.xml, 
    file_name=f'{page.name}.xml'
)
```

### worker.py

This module contains the action-specific processing logic. It runs in a separate process from the FastAPI application and communicates with `runner.py` through a `multiprocessing.Pipe`.

#### Define worker input

`WorkerRequest` describes the data that the worker needs to process one page. For example:
```python
@dataclass
class WorkerRequest: 
    image: bytes 
    xml: bytes
```

#### Define worker output
`WorkerSuccess` describes the output produced when processing succeeds:
```python
@dataclass
class WorkerSuccess: 
    xml: bytes
```

#### Initialize worker dependencies

The worker is started once per action. The template provides a dedicated location for imports and initialization. Expensive resources should generally be initialized here rather than for every page.

For example:
```python
def work(connection: Connection, model_path: Path) -> None:
    from my_model import Model
    model = Model(model_path)
```

#### Processing pages

The main action-specific implementation belongs here. The worker receives a `WorkerRequest`, processes it, and sends back a `WorkerSuccess`.

For example:
```python
image = process_image(request.image)
connection.send(WorkerSuccess(image=image))
```

#### Returning results

Successful results should be returned using the `WorkerSuccess` dataclass:

```python
connection.send(WorkerSuccess(...))
```

### action.yml

This file is a sample for the action definition in the frontend admin panel.
Refer to the [official documentation](https://docs.larex.kallimachos.de/actions/yaml-reference) for further help.

### compose.yml

This file is the Docker/Podman compose file to run the action as a container. It pulls the configuration from a required `.env` file (a template can be found in `template.env`).

#### Pass a GPU to the container

Add this to the compose file:
```yaml
devices:
  - nvidia.com/gpu=all
security_opt:
  - label=disable
```

#### Pass files or directories to the container

For example, add this to the compose file:
```yaml
volumes:
  - /storage/workspace/shared/project/models/sbbbin:/models
```

## Environment variables

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