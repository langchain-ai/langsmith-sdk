[**langsmith**](../../README.md) • **Docs**

***

[langsmith](../../README.md) / [schemas](../README.md) / Run

# Interface: Run

Describes properties of a run when loaded from the database.
Extends the BaseRun interface.

## Extends

- [`BaseRun`](BaseRun.md)

## Properties

### app\_path?

> `optional` **app\_path**: `string`

The URL path where this run is accessible within the app.

#### Defined in

[src/schemas.ts:161](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L161)

***

### child\_run\_ids?

> `optional` **child\_run\_ids**: `string`[]

IDs of any child runs spawned by this run.

#### Defined in

[src/schemas.ts:152](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L152)

***

### child\_runs?

> `optional` **child\_runs**: [`Run`](Run.md)[]

Child runs, loaded explicitly via a heavier query.

#### Defined in

[src/schemas.ts:155](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L155)

***

### completion\_tokens?

> `optional` **completion\_tokens**: `number`

Number of tokens generated in the completion.

#### Defined in

[src/schemas.ts:173](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L173)

***

### dotted\_order?

> `optional` **dotted\_order**: `string`

The dotted order for the run.

This is a string composed of {time}{run-uuid}.* so that a trace can be
sorted in the order it was executed.

Example:
- Parent: 20230914T223155647Z1b64098b-4ab7-43f6-afee-992304f198d8
- Children:
   - 20230914T223155647Z1b64098b-4ab7-43f6-afee-992304f198d8.20230914T223155649Z809ed3a2-0172-4f4d-8a02-a64e9b7a0f8a
  - 20230915T223155647Z1b64098b-4ab7-43f6-afee-992304f198d8.20230914T223155650Zc8d9f4c5-6c5a-4b2d-9b1c-3d9d7a7c5c7c

#### Inherited from

[`BaseRun`](BaseRun.md).[`dotted_order`](BaseRun.md#dotted_order)

#### Defined in

[src/schemas.ts:128](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L128)

***

### end\_time?

> `optional` **end\_time**: `number`

The epoch time at which the run ended, if applicable.

#### Inherited from

[`BaseRun`](BaseRun.md).[`end_time`](BaseRun.md#end_time)

#### Defined in

[src/schemas.ts:84](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L84)

***

### error?

> `optional` **error**: `string`

Error message, captured if the run faces any issues.

#### Inherited from

[`BaseRun`](BaseRun.md).[`error`](BaseRun.md#error)

#### Defined in

[src/schemas.ts:90](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L90)

***

### events?

> `optional` **events**: [`KVMap`](../type-aliases/KVMap.md)[]

Events like 'start', 'end' linked to the run.

#### Inherited from

[`BaseRun`](BaseRun.md).[`events`](BaseRun.md#events)

#### Defined in

[src/schemas.ts:96](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L96)

***

### extra?

> `optional` **extra**: [`KVMap`](../type-aliases/KVMap.md)

Any additional metadata or settings for the run.

#### Inherited from

[`BaseRun`](BaseRun.md).[`extra`](BaseRun.md#extra)

#### Defined in

[src/schemas.ts:87](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L87)

***

### feedback\_stats?

> `optional` **feedback\_stats**: [`KVMap`](../type-aliases/KVMap.md)

Stats capturing feedback for this run.

#### Defined in

[src/schemas.ts:158](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L158)

***

### first\_token\_time?

> `optional` **first\_token\_time**: `number`

Time when the first token was processed.

#### Defined in

[src/schemas.ts:179](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L179)

***

### id

> **id**: `string`

A unique identifier for the run, mandatory when loaded from DB.

#### Overrides

[`BaseRun`](BaseRun.md).[`id`](BaseRun.md#id)

#### Defined in

[src/schemas.ts:146](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L146)

***

### in\_dataset?

> `optional` **in\_dataset**: `boolean`

Whether the run is included in a dataset.

#### Defined in

[src/schemas.ts:185](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L185)

***

### inputs

> **inputs**: [`KVMap`](../type-aliases/KVMap.md)

Inputs that were used to initiate the run.

#### Inherited from

[`BaseRun`](BaseRun.md).[`inputs`](BaseRun.md#inputs)

#### Defined in

[src/schemas.ts:99](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L99)

***

### inputs\_s3\_urls?

> `optional` **inputs\_s3\_urls**: `S3URL`

The input S3 URLs

#### Defined in

[src/schemas.ts:191](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L191)

***

### manifest\_id?

> `optional` **manifest\_id**: `string`

The manifest ID that correlates with this run.

#### Defined in

[src/schemas.ts:164](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L164)

***

### name

> **name**: `string`

A human-readable name for the run.

#### Inherited from

[`BaseRun`](BaseRun.md).[`name`](BaseRun.md#name)

#### Defined in

[src/schemas.ts:75](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L75)

***

### outputs?

> `optional` **outputs**: [`KVMap`](../type-aliases/KVMap.md)

Outputs produced by the run, if any.

#### Inherited from

[`BaseRun`](BaseRun.md).[`outputs`](BaseRun.md#outputs)

#### Defined in

[src/schemas.ts:102](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L102)

***

### outputs\_s3\_urls?

> `optional` **outputs\_s3\_urls**: `S3URL`

The output S3 URLs

#### Defined in

[src/schemas.ts:188](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L188)

***

### parent\_run\_id?

> `optional` **parent\_run\_id**: `string`

ID of a parent run, if this run is part of a larger operation.

#### Inherited from

[`BaseRun`](BaseRun.md).[`parent_run_id`](BaseRun.md#parent_run_id)

#### Defined in

[src/schemas.ts:108](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L108)

***

### parent\_run\_ids?

> `optional` **parent\_run\_ids**: `string`[]

IDs of parent runs, if multiple exist.

#### Defined in

[src/schemas.ts:182](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L182)

***

### prompt\_tokens?

> `optional` **prompt\_tokens**: `number`

Number of tokens used in the prompt.

#### Defined in

[src/schemas.ts:170](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L170)

***

### reference\_example\_id?

> `optional` **reference\_example\_id**: `string`

ID of an example that might be related to this run.

#### Inherited from

[`BaseRun`](BaseRun.md).[`reference_example_id`](BaseRun.md#reference_example_id)

#### Defined in

[src/schemas.ts:105](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L105)

***

### run\_type

> **run\_type**: `string`

Specifies the type of run (tool, chain, llm, etc.).

#### Inherited from

[`BaseRun`](BaseRun.md).[`run_type`](BaseRun.md#run_type)

#### Defined in

[src/schemas.ts:81](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L81)

***

### serialized?

> `optional` **serialized**: `object`

Serialized state of the run for potential future use.

#### Inherited from

[`BaseRun`](BaseRun.md).[`serialized`](BaseRun.md#serialized)

#### Defined in

[src/schemas.ts:93](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L93)

***

### session\_id?

> `optional` **session\_id**: `string`

The ID of the project that owns this run.

#### Defined in

[src/schemas.ts:149](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L149)

***

### start\_time?

> `optional` **start\_time**: `number`

The epoch time at which the run started, if available.

#### Inherited from

[`BaseRun`](BaseRun.md).[`start_time`](BaseRun.md#start_time)

#### Defined in

[src/schemas.ts:78](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L78)

***

### status?

> `optional` **status**: `string`

The current status of the run, such as 'success'.

#### Defined in

[src/schemas.ts:167](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L167)

***

### tags?

> `optional` **tags**: `string`[]

Tags for further categorizing or annotating the run.

#### Inherited from

[`BaseRun`](BaseRun.md).[`tags`](BaseRun.md#tags)

#### Defined in

[src/schemas.ts:111](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L111)

***

### total\_tokens?

> `optional` **total\_tokens**: `number`

Total token count, combining prompt and completion.

#### Defined in

[src/schemas.ts:176](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L176)

***

### trace\_id?

> `optional` **trace\_id**: `string`

Unique ID assigned to every run within this nested trace. *

#### Inherited from

[`BaseRun`](BaseRun.md).[`trace_id`](BaseRun.md#trace_id)

#### Defined in

[src/schemas.ts:114](https://github.com/langchain-ai/langsmith-sdk/blob/da3c1bb4f1396b48909bf0abac53fd717458c764/js/src/schemas.ts#L114)
