import axiosClient from "./axiosClient";

export const publicApi = {
  businesses: () => axiosClient.get("/accounts/public/businesses/"),
};

export default publicApi;
