// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import * as BoxesAPI from './boxes.js';
import {
  BoxCreateParams,
  BoxCreateResponse,
  BoxCreateSnapshotParams,
  BoxCreateSnapshotResponse,
  BoxGenerateServiceURLParams,
  BoxGenerateServiceURLResponse,
  BoxGetStatusResponse,
  BoxListParams,
  BoxListResponse,
  BoxRetrieveResponse,
  BoxStartResponse,
  BoxUpdateParams,
  BoxUpdateResponse,
  Boxes,
} from './boxes.js';
import * as SnapshotsAPI from './snapshots.js';
import {
  SnapshotCreateParams,
  SnapshotCreateResponse,
  SnapshotListParams,
  SnapshotListResponse,
  SnapshotRetrieveResponse,
  Snapshots,
} from './snapshots.js';

export class Sandboxes extends APIResource {
  boxes: BoxesAPI.Boxes = new BoxesAPI.Boxes(this._client);
  snapshots: SnapshotsAPI.Snapshots = new SnapshotsAPI.Snapshots(this._client);
}

Sandboxes.Boxes = Boxes;
Sandboxes.Snapshots = Snapshots;

export declare namespace Sandboxes {
  export {
    Boxes as Boxes,
    type BoxCreateResponse as BoxCreateResponse,
    type BoxRetrieveResponse as BoxRetrieveResponse,
    type BoxUpdateResponse as BoxUpdateResponse,
    type BoxListResponse as BoxListResponse,
    type BoxCreateSnapshotResponse as BoxCreateSnapshotResponse,
    type BoxGenerateServiceURLResponse as BoxGenerateServiceURLResponse,
    type BoxGetStatusResponse as BoxGetStatusResponse,
    type BoxStartResponse as BoxStartResponse,
    type BoxCreateParams as BoxCreateParams,
    type BoxUpdateParams as BoxUpdateParams,
    type BoxListParams as BoxListParams,
    type BoxCreateSnapshotParams as BoxCreateSnapshotParams,
    type BoxGenerateServiceURLParams as BoxGenerateServiceURLParams,
  };

  export {
    Snapshots as Snapshots,
    type SnapshotCreateResponse as SnapshotCreateResponse,
    type SnapshotRetrieveResponse as SnapshotRetrieveResponse,
    type SnapshotListResponse as SnapshotListResponse,
    type SnapshotCreateParams as SnapshotCreateParams,
    type SnapshotListParams as SnapshotListParams,
  };
}
