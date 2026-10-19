import { proxyRead, denyWrite } from "../proxy";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 60;
export async function GET(request: Request, context: { params: Promise<{ path: string[] }> }) {
  return proxyRead(request, (await context.params).path);
}
export function POST() {
  return denyWrite();
}
export function PUT() {
  return denyWrite();
}
export function PATCH() {
  return denyWrite();
}
export function DELETE() {
  return denyWrite();
}
