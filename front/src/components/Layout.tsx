import React, { useState } from "react";
import { Layout, Menu, Button, Typography, theme } from "antd";
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAppContext } from "../context/AppContext";
import HeaderWidget from "./HeaderWidget";
import {
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  DashboardOutlined,
  DesktopOutlined,
  SettingOutlined,
  UserOutlined,
  BarsOutlined,
} from "@ant-design/icons";

const { Sider, Content, Header } = Layout;

const AppLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const location = useLocation();
  const { t } = useTranslation();
  const { pageTitle, dark } = useAppContext();
  const [collapsed, setCollapsed] = useState(false);
  const { token } = theme.useToken();

  return (
    <Layout
      style={{
        minHeight: "100vh",
        marginLeft: collapsed ? 80 : 200,
        background: token.colorBgLayout,
      }}
    >
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        trigger={null}
        style={{
          position: "fixed",
          height: "100vh",
          left: 0,
          top: 0,
          bottom: 0,
          zIndex: 1000,
          background: token.colorBgContainer,
        }}
      >
        <Button
          type="text"
          icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          onClick={() => setCollapsed(!collapsed)}
          style={{
            color: token.colorText,
            width: "100%",
            textAlign: "left",
            padding: "16px",
            borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
            position: "absolute",
            top: 0,
            zIndex: 1000,
          }}
          aria-label={collapsed ? t("expand_menu", "Розгорнути меню") : t("collapse_menu", "Згорнути меню")}
        >
          {!collapsed && t(collapsed ? "expand_menu" : "collapse_menu", collapsed ? "Розгорнути меню" : "Згорнути меню")}
        </Button>
        <Menu
          theme={dark ? "dark" : "light"}
          mode="inline"
          selectedKeys={[location.pathname]}
          items={[
            {
              key: "/",
              icon: <DashboardOutlined />,
              label: <Link to="/">{t("dashboard", "Панель керування")}</Link>,
            },
            {
              key: "/computers",
              icon: <DesktopOutlined />,
              label: <Link to="/computers">{t("computers", "Комп’ютери")}</Link>,
            },
            {
              key: "/admin",
              icon: <UserOutlined />,
              label: <Link to="/admin">{t("admin", "Адмін")}</Link>,
            },
            {
              key: "/settings",
              icon: <SettingOutlined />,
              label: <Link to="/settings">{t("settings", "Налаштування")}</Link>,
            },
            {
              key: "/tasks",
              icon: <BarsOutlined />,
              label: <Link to="/tasks">{t("tasks", "Завдання")}</Link>,
            },
          ]}
          style={{ paddingTop: "56px" }}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            padding: "0 20px",
            background: token.colorBgContainer,
            height: "48px",
            lineHeight: "30px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <Typography.Title level={4} style={{ margin: 0 }}>
            {pageTitle || t("app_title", "Inventory Management")}
          </Typography.Title>
          <div style={{ position: "absolute", top: 0, right: 0 }}>
            <HeaderWidget />
          </div>
        </Header>
        <Content
          style={{
            margin: 0,
            padding: "10px",
            minHeight: "calc(100vh - 48px)",
            background: token.colorBgLayout,
          }}
        >
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;