---
sidebar_label: client
title: client
---

#### close\_session

```python
def close_session(session: Session) -> None
```

Close the session.

Parameters
----------
session : Session
    The session to close.

## Client Objects

```python
class Client()
```

Client for interacting with the LangSmith API.

#### \_\_init\_\_

```python
def __init__(api_url: Optional[str] = None,
             *,
             api_key: Optional[str] = None,
             retry_config: Optional[Retry] = None,
             timeout_ms: Optional[int] = None) -> None
```

Initialize a Client instance.

Parameters
----------
api_url : str or None, default=None
    URL for the LangSmith API. Defaults to the LANGCHAIN_ENDPOINT
    environment variable or http://localhost:1984 if not set.
api_key : str or None, default=None
    API key for the LangSmith API. Defaults to the LANGCHAIN_API_KEY
    environment variable.
retry_config : Retry or None, default=None
    Retry configuration for the HTTPAdapter.
timeout_ms : int or None, default=None
    Timeout in milliseconds for the HTTPAdapter.

Raises
------
LangSmithUserError
    If the API key is not provided when using the hosted service.

#### \_repr\_html\_

```python
def _repr_html_() -> str
```

Return an HTML representation of the instance with a link to the URL.

Returns
-------
str
    The HTML representation of the instance.

#### \_\_repr\_\_

```python
def __repr__() -> str
```

Return a string representation of the instance with a link to the URL.

Returns
-------
str
    The string representation of the instance.

#### request\_with\_retries

```python
def request_with_retries(request_method: str, url: str,
                         request_kwargs: Mapping) -> Response
```

Send a request with retries.

Parameters
----------
request_method : str
    The HTTP request method.
url : str
    The URL to send the request to.
request_kwargs : Mapping
    Additional request parameters.

Returns
-------
Response
    The response object.

Raises
------
LangSmithAPIError
    If a server error occurs.
LangSmithUserError
    If the request fails.
LangSmithConnectionError
    If a connection error occurs.
LangSmithError
    If the request fails.

#### upload\_dataframe

```python
def upload_dataframe(df: pd.DataFrame,
                     name: str,
                     input_keys: Sequence[str],
                     output_keys: Sequence[str],
                     *,
                     description: Optional[str] = None,
                     data_type: Optional[DataType] = DataType.kv) -> Dataset
```

Upload a dataframe as individual examples to the LangSmith API.

Parameters
----------
df : pd.DataFrame
    The dataframe to upload.
name : str
    The name of the dataset.
input_keys : Sequence[str]
    The input keys.
output_keys : Sequence[str]
    The output keys.
description : str or None, default=None
    The description of the dataset.
data_type : DataType or None, default=DataType.kv
    The data type of the dataset.

Returns
-------
Dataset
    The uploaded dataset.

Raises
------
ValueError
    If the csv_file is not a string or tuple.

#### upload\_csv

```python
def upload_csv(csv_file: Union[str, Tuple[str, BytesIO]],
               input_keys: Sequence[str],
               output_keys: Sequence[str],
               *,
               name: Optional[str] = None,
               description: Optional[str] = None,
               data_type: Optional[DataType] = DataType.kv) -> Dataset
```

Upload a CSV file to the LangSmith API.

Parameters
----------
csv_file : str or Tuple[str, BytesIO]
    The CSV file to upload. If a string, it should be the path
    If a tuple, it should be a tuple containing the filename
    and a BytesIO object.
input_keys : Sequence[str]
    The input keys.
output_keys : Sequence[str]
    The output keys.
name : str or None, default=None
    The name of the dataset.
description : str or None, default=None
    The description of the dataset.
data_type : DataType or None, default=DataType.kv
    The data type of the dataset.

Returns
-------
Dataset
    The uploaded dataset.

Raises
------
ValueError
    If the csv_file is not a string or tuple.

#### create\_run

```python
def create_run(name: str,
               inputs: Dict[str, Any],
               run_type: str,
               *,
               execution_order: Optional[int] = None,
               **kwargs: Any) -> None
```

Persist a run to the LangSmith API.

Parameters
----------
name : str
    The name of the run.
inputs : Dict[str, Any]
    The input values for the run.
run_type : str
    The type of the run, such as  such as tool, chain, llm, retriever,
    embedding, prompt, or parser.
execution_order : int or None, default=None
    The execution order of the run.
**kwargs : Any
    Additional keyword arguments.

Raises
------
LangSmithUserError
    If the API key is not provided when using the hosted service.

#### update\_run

```python
def update_run(run_id: ID_TYPE, **kwargs: Any) -> None
```

Update a run in the LangSmith API.

Parameters
----------
run_id : str or UUID
    The ID of the run to update.
**kwargs : Any
    Additional keyword arguments.

#### read\_run

```python
def read_run(run_id: ID_TYPE, load_child_runs: bool = False) -> Run
```

Read a run from the LangSmith API.

Parameters
----------
run_id : str or UUID
    The ID of the run to read.
load_child_runs : bool, default=False
    Whether to load nested child runs.

Returns
-------
Run
    The run.

#### list\_runs

```python
def list_runs(*,
              project_id: Optional[ID_TYPE] = None,
              project_name: Optional[str] = None,
              run_type: Optional[str] = None,
              dataset_name: Optional[str] = None,
              dataset_id: Optional[ID_TYPE] = None,
              reference_example_id: Optional[ID_TYPE] = None,
              query: Optional[str] = None,
              filter: Optional[str] = None,
              execution_order: Optional[int] = None,
              parent_run_id: Optional[ID_TYPE] = None,
              start_time: Optional[datetime] = None,
              end_time: Optional[datetime] = None,
              error: Optional[bool] = None,
              run_ids: Optional[List[ID_TYPE]] = None,
              limit: Optional[int] = None,
              offset: Optional[int] = None,
              order_by: Optional[Sequence[str]] = None,
              **kwargs: Any) -> Iterator[Run]
```

List runs from the LangSmith API.

Parameters
----------
project_id : UUID or None, default=None
    The ID of the project to filter by.
project_name : str or None, default=None
    The name of the project to filter by.
run_type : str or None, default=None
    The type of the runs to filter by.
dataset_name : str or None, default=None
    The name of the dataset to filter by.
dataset_id : UUID or None, default=None
    The ID of the dataset to filter by.
reference_example_id : UUID or None, default=None
    The ID of the reference example to filter by.
query : str or None, default=None
    The query string to filter by.
filter : str or None, default=None
    The filter string to filter by.
execution_order : int or None, default=None
    The execution order to filter by.
parent_run_id : UUID or None, default=None
    The ID of the parent run to filter by.
start_time : datetime or None, default=None
    The start time to filter by.
end_time : datetime or None, default=None
    The end time to filter by.
error : bool or None, default=None
    Whether to filter by error status.
run_ids : List[str or UUID] or None, default=None
    The IDs of the runs to filter by.
limit : int or None, default=None
    The maximum number of runs to return.
offset : int or None, default=None
    The number of runs to skip.
order_by : Sequence[str] or None, default=None
    The fields to order the runs by.
**kwargs : Any
    Additional keyword arguments.

Yields
------
Run
    The runs.

#### delete\_run

```python
def delete_run(run_id: ID_TYPE) -> None
```

Delete a run from the LangSmith API.

Parameters
----------
run_id : str or UUID
    The ID of the run to delete.

#### share\_run

```python
def share_run(run_id: ID_TYPE, *, share_id: Optional[ID_TYPE] = None) -> str
```

Get a share link for a run.

#### unshare\_run

```python
def unshare_run(run_id: ID_TYPE) -> None
```

Delete share link for a run.

#### run\_is\_shared

```python
def run_is_shared(run_id: ID_TYPE) -> bool
```

Get share state for a run.

#### create\_project

```python
def create_project(project_name: str,
                   *,
                   project_extra: Optional[dict] = None,
                   upsert: bool = False) -> TracerSession
```

Create a project on the LangSmith API.

Parameters
----------
project_name : str
    The name of the project.
project_extra : dict or None, default=None
    Additional project information.
upsert : bool, default=False
    Whether to update the project if it already exists.

Returns
-------
TracerSession
    The created project.

#### read\_project

```python
@xor_args(("project_id", "project_name"))
def read_project(*,
                 project_id: Optional[str] = None,
                 project_name: Optional[str] = None) -> TracerSessionResult
```

Read a project from the LangSmith API.

Parameters
----------
project_id : str or None, default=None
    The ID of the project to read.
project_name : str or None, default=None
    The name of the project to read.
        Note: Only one of project_id or project_name may be given.

Returns
-------
TracerSessionResult
    The project.

#### list\_projects

```python
def list_projects() -> Iterator[TracerSession]
```

List projects from the LangSmith API.

Yields
------
TracerSession
    The projects.

#### delete\_project

```python
@xor_args(("project_name", "project_id"))
def delete_project(*,
                   project_name: Optional[str] = None,
                   project_id: Optional[str] = None) -> None
```

Delete a project from the LangSmith API.

Parameters
----------
project_name : str or None, default=None
    The name of the project to delete.
project_id : str or None, default=None
    The ID of the project to delete.

#### create\_dataset

```python
def create_dataset(dataset_name: str,
                   *,
                   description: Optional[str] = None,
                   data_type: DataType = DataType.kv) -> Dataset
```

Create a dataset in the LangSmith API.

Parameters
----------
dataset_name : str
    The name of the dataset.
description : str or None, default=None
    The description of the dataset.
data_type : DataType or None, default=DataType.kv
    The data type of the dataset.

Returns
-------
Dataset
    The created dataset.

#### read\_dataset

```python
@xor_args(("dataset_name", "dataset_id"))
def read_dataset(*,
                 dataset_name: Optional[str] = None,
                 dataset_id: Optional[ID_TYPE] = None) -> Dataset
```

Read a dataset from the LangSmith API.

Parameters
----------
dataset_name : str or None, default=None
    The name of the dataset to read.
dataset_id : UUID or None, default=None
    The ID of the dataset to read.

Returns
-------
Dataset
    The dataset.

#### list\_datasets

```python
def list_datasets(
        *,
        dataset_ids: Optional[List[ID_TYPE]] = None,
        data_type: Optional[str] = None,
        dataset_name: Optional[str] = None,
        dataset_name_contains: Optional[str] = None) -> Iterator[Dataset]
```

List the datasets on the LangSmith API.

Yields
------
Dataset
    The datasets.

#### delete\_dataset

```python
@xor_args(("dataset_id", "dataset_name"))
def delete_dataset(*,
                   dataset_id: Optional[ID_TYPE] = None,
                   dataset_name: Optional[str] = None) -> None
```

Delete a dataset from the LangSmith API.

Parameters
----------
dataset_id : UUID or None, default=None
    The ID of the dataset to delete.
dataset_name : str or None, default=None
    The name of the dataset to delete.

#### create\_llm\_example

```python
@xor_args(("dataset_id", "dataset_name"))
def create_llm_example(prompt: str,
                       generation: Optional[str] = None,
                       dataset_id: Optional[ID_TYPE] = None,
                       dataset_name: Optional[str] = None,
                       created_at: Optional[datetime] = None) -> Example
```

Add an example (row) to an LLM-type dataset.

#### create\_chat\_example

```python
@xor_args(("dataset_id", "dataset_name"))
def create_chat_example(messages: List[Mapping[str, Any]],
                        generations: Optional[Mapping[str, Any]] = None,
                        dataset_id: Optional[ID_TYPE] = None,
                        dataset_name: Optional[str] = None,
                        created_at: Optional[datetime] = None) -> Example
```

Add an example (row) to a Chat-type dataset.

#### create\_example\_from\_run

```python
def create_example_from_run(run: Run,
                            dataset_id: Optional[ID_TYPE] = None,
                            dataset_name: Optional[str] = None,
                            created_at: Optional[datetime] = None) -> Example
```

Add an example (row) to an LLM-type dataset.

#### create\_example

```python
@xor_args(("dataset_id", "dataset_name"))
def create_example(inputs: Mapping[str, Any],
                   dataset_id: Optional[ID_TYPE] = None,
                   dataset_name: Optional[str] = None,
                   created_at: Optional[datetime] = None,
                   outputs: Optional[Mapping[str, Any]] = None) -> Example
```

Create a dataset example in the LangSmith API.

Parameters
----------
inputs : Mapping[str, Any]
    The input values for the example.
dataset_id : UUID or None, default=None
    The ID of the dataset to create the example in.
dataset_name : str or None, default=None
    The name of the dataset to create the example in.
created_at : datetime or None, default=None
    The creation timestamp of the example.
outputs : Mapping[str, Any] or None, default=None
    The output values for the example.

Returns
-------
Example
    The created example.

#### read\_example

```python
def read_example(example_id: ID_TYPE) -> Example
```

Read an example from the LangSmith API.

Parameters
----------
example_id : str or UUID
    The ID of the example to read.

Returns
-------
Example
    The example.

#### list\_examples

```python
def list_examples(
        dataset_id: Optional[ID_TYPE] = None,
        dataset_name: Optional[str] = None,
        example_ids: Optional[List[ID_TYPE]] = None) -> Iterator[Example]
```

List the examples on the LangSmith API.

Parameters
----------
dataset_id : UUID or None, default=None
    The ID of the dataset to filter by.
dataset_name : str or None, default=None
    The name of the dataset to filter by.
example_ids : List[UUID] or None, default=None
    The IDs of the examples to filter by.

Yields
------
Example
    The examples.

#### update\_example

```python
def update_example(example_id: str,
                   *,
                   inputs: Optional[Dict[str, Any]] = None,
                   outputs: Optional[Mapping[str, Any]] = None,
                   dataset_id: Optional[ID_TYPE] = None) -> Dict[str, Any]
```

Update a specific example.

Parameters
----------
example_id : str or UUID
    The ID of the example to update.
inputs : Dict[str, Any] or None, default=None
    The input values to update.
outputs : Mapping[str, Any] or None, default=None
    The output values to update.
dataset_id : UUID or None, default=None
    The ID of the dataset to update.

Returns
-------
Dict[str, Any]
    The updated example.

#### delete\_example

```python
def delete_example(example_id: ID_TYPE) -> None
```

Delete an example by ID.

Parameters
----------
example_id : str or UUID
    The ID of the example to delete.

#### evaluate\_run

```python
def evaluate_run(run: Union[Run, RunBase, str, UUID],
                 evaluator: RunEvaluator,
                 *,
                 source_info: Optional[Dict[str, Any]] = None,
                 reference_example: Optional[Union[Example, str, dict,
                                                   UUID]] = None,
                 load_child_runs: bool = False) -> Feedback
```

Evaluate a run.

Parameters
----------
run : Run or RunBase or str or UUID
    The run to evaluate.
evaluator : RunEvaluator
    The evaluator to use.
source_info : Dict[str, Any] or None, default=None
    Additional information about the source of the evaluation to log
    as feedback metadata.
reference_example : Example or str or dict or UUID or None, default=None
    The example to use as a reference for the evaluation.
    If not provided, the run&#x27;s reference example will be used.
load_child_runs : bool, default=False
    Whether to load child runs when resolving the run ID.

Returns
-------
Feedback
    The feedback object created by the evaluation.

#### aevaluate\_run

```python
async def aevaluate_run(run: Union[Run, str, UUID],
                        evaluator: RunEvaluator,
                        *,
                        source_info: Optional[Dict[str, Any]] = None,
                        reference_example: Optional[Union[Example, str, dict,
                                                          UUID]] = None,
                        load_child_runs: bool = False) -> Feedback
```

Evaluate a run asynchronously.

Parameters
----------
run : Run or str or UUID
    The run to evaluate.
evaluator : RunEvaluator
    The evaluator to use.
source_info : Dict[str, Any] or None, default=None
    Additional information about the source of the evaluation to log
    as feedback metadata.
reference_example : Optional Example or UUID, default=None
    The example to use as a reference for the evaluation.
    If not provided, the run&#x27;s reference example will be used.
load_child_runs : bool, default=False
    Whether to load child runs when resolving the run ID.

Returns
-------
Feedback
    The feedback created by the evaluation.

#### create\_feedback

```python
def create_feedback(run_id: ID_TYPE,
                    key: str,
                    *,
                    score: Union[float, int, bool, None] = None,
                    value: Union[float, int, bool, str, dict, None] = None,
                    correction: Union[dict, None] = None,
                    comment: Union[str, None] = None,
                    source_info: Optional[Dict[str, Any]] = None,
                    feedback_source_type: Union[FeedbackSourceType,
                                                str] = FeedbackSourceType.API,
                    source_run_id: Optional[ID_TYPE] = None) -> Feedback
```

Create a feedback in the LangSmith API.

Parameters
----------
run_id : str or UUID
    The ID of the run to provide feedback on.
key : str
    The name of the metric, tag, or &#x27;aspect&#x27; this feedback is about.
score : float or int or bool or None, default=None
    The score to rate this run on the metric or aspect.
value : float or int or bool or str or dict or None, default=None
    The display value or non-numeric value for this feedback.
correction : dict or None, default=None
    The proper ground truth for this run.
comment : str or None, default=None
    A comment about this feedback.
source_info : Dict[str, Any] or None, default=None
    Information about the source of this feedback.
feedback_source_type : FeedbackSourceType or str, default=FeedbackSourceType.API
    The type of feedback source.
source_run_id : str or UUID or None, default=None,
    The ID of the run that generated this feedback, if a &quot;model&quot; type.

Returns
-------
Feedback
    The created feedback.

#### update\_feedback

```python
def update_feedback(feedback_id: ID_TYPE,
                    *,
                    score: Union[float, int, bool, None] = None,
                    value: Union[float, int, bool, str, dict, None] = None,
                    correction: Union[dict, None] = None,
                    comment: Union[str, None] = None) -> Feedback
```

Update a feedback in the LangSmith API.

Parameters
----------
feedback_id : str or UUID
    The ID of the feedback to update.
score : float or int or bool or None, default=None
    The score to update the feedback with.
value : float or int or bool or str or dict or None, default=None
    The value to update the feedback with.
correction : dict or None, default=None
    The correction to update the feedback with.
comment : str or None, default=None
    The comment to update the feedback with.

Returns
-------
Feedback
    The updated feedback.

#### read\_feedback

```python
def read_feedback(feedback_id: ID_TYPE) -> Feedback
```

Read a feedback from the LangSmith API.

Parameters
----------
feedback_id : str or UUID
    The ID of the feedback to read.

Returns
-------
Feedback
    The feedback.

#### list\_feedback

```python
def list_feedback(*,
                  run_ids: Optional[Sequence[ID_TYPE]] = None,
                  **kwargs: Any) -> Iterator[Feedback]
```

List the feedback objects on the LangSmith API.

Parameters
----------
run_ids : List[str or UUID] or None, default=None
    The IDs of the runs to filter by.
**kwargs : Any
    Additional keyword arguments.

Yields
------
Feedback
    The feedback objects.

#### delete\_feedback

```python
def delete_feedback(feedback_id: ID_TYPE) -> None
```

Delete a feedback by ID.

Parameters
----------
feedback_id : str or UUID
    The ID of the feedback to delete.

#### arun\_on\_dataset

```python
async def arun_on_dataset(
        dataset_name: str,
        llm_or_chain_factory: Any,
        *,
        evaluation: Optional[Any] = None,
        concurrency_level: int = 5,
        project_name: Optional[str] = None,
        verbose: bool = False,
        tags: Optional[List[str]] = None,
        input_mapper: Optional[Callable[[Dict],
                                        Any]] = None) -> Dict[str, Any]
```

Asynchronously run the Chain or language model on a dataset
and store traces to the specified project name.

Args:
    dataset_name: Name of the dataset to run the chain on.
    llm_or_chain_factory: Language model or Chain constructor to run
        over the dataset. The Chain constructor is used to permit
        independent calls on each example without carrying over state.
    evaluation: Optional evaluation configuration to use when evaluating
    concurrency_level: The number of async tasks to run concurrently.
    project_name: Name of the project to store the traces in.
        Defaults to {dataset_name}-{chain class name}-{datetime}.
    verbose: Whether to print progress.
    tags: Tags to add to each run in the project.
    input_mapper: A function to map to the inputs dictionary from an Example
        to the format expected by the model to be evaluated. This is useful if
        your model needs to deserialize more complex schema or if your dataset
        has inputs with keys that differ from what is expected by your chain
        or agent.

Returns:
    A dictionary containing the run&#x27;s project name and the
    resulting model outputs.

For the synchronous version, see client.run_on_dataset.

Examples
--------

.. code-block:: python

    from langsmith import Client
    from langchain.chat_models import ChatOpenAI
    from langchain.chains import LLMChain
    from langchain.smith import RunEvalConfig

    # Chains may have memory. Passing in a constructor function lets the
    # evaluation framework avoid cross-contamination between runs.
    def construct_chain():
        llm = ChatOpenAI(temperature=0)
        chain = LLMChain.from_string(
            llm,
            &quot;What&#x27;s the answer to {your_input_key}&quot;
        )
        return chain

    # Load off-the-shelf evaluators via config or the EvaluatorType (string or enum)
    evaluation_config = RunEvalConfig(
        evaluators=[
            &quot;qa&quot;,  # &quot;Correctness&quot; against a reference answer
            &quot;embedding_distance&quot;,
            RunEvalConfig.Criteria(&quot;helpfulness&quot;),
            RunEvalConfig.Criteria({
                &quot;fifth-grader-score&quot;: &quot;Do you have to be smarter than a fifth grader to answer this question?&quot;
            }),
        ]
    )

    client = Client()
    await client.arun_on_dataset(
        &quot;&lt;my_dataset_name&gt;&quot;,
        construct_chain,
        evaluation=evaluation_config,
    )

You can also create custom evaluators by subclassing the
:class:`StringEvaluator <langchain.evaluation.schema.StringEvaluator>`
or LangSmith&#x27;s `RunEvaluator` classes.

.. code-block:: python

    from typing import Optional
    from langchain.evaluation import StringEvaluator

    class MyStringEvaluator(StringEvaluator):

        @property
        def requires_input(self) -&gt; bool:
            return False

        @property
        def requires_reference(self) -&gt; bool:
            return True

        @property
        def evaluation_name(self) -&gt; str:
            return &quot;exact_match&quot;

        def _evaluate_strings(self, prediction, reference=None, input=None, **kwargs) -&gt; dict:
            return {&quot;score&quot;: prediction == reference}


    evaluation_config = RunEvalConfig(
        custom_evaluators = [MyStringEvaluator()],
    )

    await client.arun_on_dataset(
        &quot;&lt;my_dataset_name&gt;&quot;,
        construct_chain,
        evaluation=evaluation_config,
    )

#### run\_on\_dataset

```python
def run_on_dataset(
        dataset_name: str,
        llm_or_chain_factory: Any,
        *,
        evaluation: Optional[Any] = None,
        project_name: Optional[str] = None,
        verbose: bool = False,
        tags: Optional[List[str]] = None,
        input_mapper: Optional[Callable[[Dict],
                                        Any]] = None) -> Dict[str, Any]
```

Run the Chain or language model on a dataset and store traces
to the specified project name.

Args:
    dataset_name: Name of the dataset to run the chain on.
    llm_or_chain_factory: Language model or Chain constructor to run
        over the dataset. The Chain constructor is used to permit
        independent calls on each example without carrying over state.
    evaluation: Configuration for evaluators to run on the
        results of the chain
    project_name: Name of the project to store the traces in.
        Defaults to {dataset_name}-{chain class name}-{datetime}.
    verbose: Whether to print progress.
    tags: Tags to add to each run in the project.
    input_mapper: A function to map to the inputs dictionary from an Example
        to the format expected by the model to be evaluated. This is useful if
        your model needs to deserialize more complex schema or if your dataset
        has inputs with keys that differ from what is expected by your chain
        or agent.

Returns:
    A dictionary containing the run&#x27;s project name and the resulting model outputs.


For the (usually faster) async version of this function, see `client.arun_on_dataset`.

Examples
--------

.. code-block:: python

    from langsmith import Client
    from langchain.chat_models import ChatOpenAI
    from langchain.chains import LLMChain
    from langchain.smith import RunEvalConfig

    # Chains may have memory. Passing in a constructor function lets the
    # evaluation framework avoid cross-contamination between runs.
    def construct_chain():
        llm = ChatOpenAI(temperature=0)
        chain = LLMChain.from_string(
            llm,
            &quot;What&#x27;s the answer to {your_input_key}&quot;
        )
        return chain

    # Load off-the-shelf evaluators via config or the EvaluatorType (string or enum)
    evaluation_config = RunEvalConfig(
        evaluators=[
            &quot;qa&quot;,  # &quot;Correctness&quot; against a reference answer
            &quot;embedding_distance&quot;,
            RunEvalConfig.Criteria(&quot;helpfulness&quot;),
            RunEvalConfig.Criteria({
                &quot;fifth-grader-score&quot;: &quot;Do you have to be smarter than a fifth grader to answer this question?&quot;
            }),
        ]
    )

    client = Client()
    client.run_on_dataset(
        &quot;&lt;my_dataset_name&gt;&quot;,
        construct_chain,
        evaluation=evaluation_config,
    )

You can also create custom evaluators by subclassing the
:class:`StringEvaluator <langchain.evaluation.schema.StringEvaluator>`
or LangSmith&#x27;s `RunEvaluator` classes.

.. code-block:: python

    from typing import Optional
    from langchain.evaluation import StringEvaluator

    class MyStringEvaluator(StringEvaluator):

        @property
        def requires_input(self) -&gt; bool:
            return False

        @property
        def requires_reference(self) -&gt; bool:
            return True

        @property
        def evaluation_name(self) -&gt; str:
            return &quot;exact_match&quot;

        def _evaluate_strings(self, prediction, reference=None, input=None, **kwargs) -&gt; dict:
            return {&quot;score&quot;: prediction == reference}


    evaluation_config = RunEvalConfig(
        custom_evaluators = [MyStringEvaluator()],
    )

    client.run_on_dataset(
        &quot;&lt;my_dataset_name&gt;&quot;,
        construct_chain,
        evaluation=evaluation_config,
    )

