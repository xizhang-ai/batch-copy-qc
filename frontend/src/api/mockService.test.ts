import { mockApi } from "./mockService";

it("keeps mock batch items isolated and exports the latest visible batch", async () => {
  const first = (await mockApi.listGenerationRuns("p-demo"))[0];
  const second = await mockApi.createGenerationRun("p-demo");

  expect(second.status).toBe("completed");
  expect((await mockApi.getBoard("p-demo", second.id)).items).toHaveLength(4);
  expect((await mockApi.getBoard("p-demo", first.id)).items).not.toHaveLength(0);

  await mockApi.setGenerationRunArchived(second.id, true);
  const exported = await mockApi.createExport("p-demo");

  expect(exported.generation_run_id).toBe(first.id);
  expect(exported.row_count).toBe(3);
});

it("rejects mock export when every generation batch is hidden", async () => {
  const runs = await mockApi.listGenerationRuns("p-demo");
  await Promise.all(runs.map((run) => mockApi.setGenerationRunArchived(run.id, true)));

  await expect(mockApi.createExport("p-demo")).rejects.toMatchObject({
    code: "VISIBLE_GENERATION_RUN_REQUIRED",
  });
});
