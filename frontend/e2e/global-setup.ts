import { randomUUID } from "crypto";
import { mkdir, writeFile } from "fs/promises";
import path from "path";

import { PrismaClient } from "../src/generated/prisma";

export default async function globalSetup() {
  const prisma = new PrismaClient();

  await prisma.generatedClip.deleteMany();
  await prisma.task.deleteMany();
  await prisma.source.deleteMany();

  const completedSource = await prisma.source.create({
    data: {
      type: "youtube",
      title: "Seeded marketing walkthrough",
      url: "https://www.youtube.com/watch?v=seeded",
    },
  });
  const queuedSource = await prisma.source.create({
    data: {
      type: "youtube",
      title: "Queued seed source",
      url: "https://www.youtube.com/watch?v=queued",
    },
  });

  const completedTask = await prisma.task.create({
    data: {
      source_id: completedSource.id,
      generated_clips_ids: [],
      status: "completed",
      progress: 100,
      progress_message: "Complete!",
      font_family: "TikTokSans-Regular",
      font_size: 24,
      font_color: "#FFFFFF",
    },
  });
  const queuedTask = await prisma.task.create({
    data: {
      source_id: queuedSource.id,
      generated_clips_ids: [],
      status: "queued",
      progress: 0,
      progress_message: "Waiting for worker",
      font_family: "TikTokSans-Regular",
      font_size: 24,
      font_color: "#FFFFFF",
    },
  });

  const clipId = randomUUID();
  await prisma.generatedClip.create({
    data: {
      id: clipId,
      task_id: completedTask.id,
      filename: "seeded-clip.mp4",
      file_path: "/tmp/seeded-clip.mp4",
      start_time: "00:00",
      end_time: "00:15",
      duration: 15,
      text: "This is a seeded clip",
      relevance_score: 0.99,
      reasoning: "Seed data for Playwright",
      clip_order: 1,
    },
  });

  await prisma.task.update({
    where: { id: completedTask.id },
    data: {
      generated_clips_ids: [clipId],
    },
  });

  const seedPath = path.join(process.cwd(), "e2e", ".seed.json");
  await mkdir(path.dirname(seedPath), { recursive: true });
  await writeFile(
    seedPath,
    JSON.stringify(
      {
        completedTaskId: completedTask.id,
        queuedTaskId: queuedTask.id,
        completedSourceTitle: completedSource.title,
      },
      null,
      2,
    ),
  );

  await prisma.$disconnect();
}
