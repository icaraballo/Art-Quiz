import { Tabs } from "expo-router";

export default function Layout() {
  return (
    <Tabs>
      <Tabs.Screen
        name="camara"
        options={{ title: "Cámara", tabBarIcon: () => null }}
      />
      <Tabs.Screen
        name="quiz"
        options={{ title: "Quiz", tabBarIcon: () => null }}
      />
    </Tabs>
  );
}
